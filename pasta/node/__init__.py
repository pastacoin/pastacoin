from __future__ import annotations

"""Pasta Node abstraction.

Encapsulates blockchain & mempool state so every front-end (CLI, GUI, REST
server) can share the same logic without global variables.

NOTE: This class is intentionally minimal – it only mirrors the behaviour that
existed previously in pasta.network.server.  Additional networking (peer-to-peer)
will be added later.
"""

import threading
import time
from typing import List, Dict, Optional

from flask import Flask  # type: ignore – optional dependency (used in start_rest_server)

from pasta.core.models import TransactionBlock
from pasta.validation import engine as ve
from pasta.core.crypto import generate_keypair as _generate_keypair

__all__ = ["Node", "create_default_app", "_generate_keypair"]


class Node:
    """In-memory blockchain node suitable for tests, REST, or GUI embedding."""

    def __init__(self) -> None:
        self.blockchain: List[Dict] = []
        self.mempool: List[Dict] = []
        self._lock = threading.Lock()

        # Guarantee genesis existence on startup
        self._ensure_genesis()

        # rolling stats for experimental minting phase
        self.tx_counter: int = 0
        self.total_amount: float = 0.0

        # Difficulty management (per-level): start at 0, retarget at BTC cadence
        self._difficulty_by_level: dict[int, int] = {0: 0}
        self._pow_durations_sec: dict[int, list[float]] = {0: []}
        self._c_blocks_since_retarget: dict[int, int] = {0: 0}
        self._RETARGET_WINDOW = 2016
        self._TARGET_BLOCK_TIME_L0 = 600.0  # seconds

    # ---------------------------------------------------------------------
    # Genesis helpers
    # ---------------------------------------------------------------------
    def _ensure_genesis(self) -> None:
        """Create the initial blockchain + State-B genesis tx in mempool."""
        if not self.blockchain:
            gen = TransactionBlock.create_genesis()
            self.blockchain.append(gen.__dict__)

        if not self.mempool:
            genesis_hash = self.blockchain[0]["block_hash"]
            gtx = TransactionBlock(
                sender_address="GENESIS",
                receiver_address="GENESIS",
                amount=0,
                timestamp=int(time.time()),
                predecessor_id=genesis_hash,
                predecessor_hash=genesis_hash,
                level=0,
                validated_block_id=genesis_hash,
                validated_block_hash=genesis_hash,
                state="B",
            )
            self.mempool.append(gtx.__dict__)

    # --------------------------- Balances ---------------------------------
    def _balance_for(self, address: str) -> float:
        if not address:
            return 0.0
        balance = 0.0
        for block in self.blockchain:
            recv = block.get("receiver_address")
            send = block.get("sender_address")
            amt = float(block.get("amount", 0.0))
            if recv == address:
                balance += amt
            if send == address and send != "GENESIS":
                balance -= amt
        return balance

    # ------------------------ Difficulty helpers --------------------------
    def _current_prefix_for_level(self, level: int) -> str:
        zeros = self._difficulty_by_level.get(level, 0)
        return "0" * max(0, int(zeros))

    def _target_block_time_for_level(self, level: int) -> float:
        # halve for each higher level; minimum 1s to avoid zero/very small
        return max(1.0, self._TARGET_BLOCK_TIME_L0 / (2 ** max(0, int(level))))

    def _maybe_retarget(self, level: int) -> None:
        produced = self._c_blocks_since_retarget.get(level, 0)
        if produced < self._RETARGET_WINDOW:
            return
        times = self._pow_durations_sec.get(level, [])
        # Reset counters even if empty
        self._c_blocks_since_retarget[level] = 0
        self._pow_durations_sec[level] = []
        if not times:
            return
        avg_time = sum(times) / len(times)
        target = self._target_block_time_for_level(level)
        if avg_time < target:
            self._difficulty_by_level[level] = self._difficulty_by_level.get(level, 0) + 1

    # ---------------------------------------------------------------------
    # Public query helpers (thread-safe)
    # ---------------------------------------------------------------------
    def get_blockchain(self) -> List[Dict]:
        with self._lock:
            return list(self.blockchain)  # shallow copy

    def get_mempool(self) -> List[Dict]:
        with self._lock:
            return list(self.mempool)

    # ------------------------------------------------------------------
    # Transaction workflow
    # ------------------------------------------------------------------
    def _average_amount(self) -> float:
        return self.total_amount / self.tx_counter if self.tx_counter else 0.0

    def create_transaction(self, sender: str, receiver: str, amount: float) -> Dict:
        """Create a State-A transaction, apply experimental minting, and add to mempool."""
        with self._lock:
            # Experimental minting: first 100k tx may be zero-value; we mint up to target 10 PASTA
            if amount == 0 and self.tx_counter < 100_000:
                mint = max(0.0, 10.0 - self._average_amount())
                amount = mint  # inject minted coins into tx
            else:
                mint = 0.0

            predecessor = TransactionBlock(**self.blockchain[-1])
            tx_obj = ve.build_state_a(sender, receiver, amount, predecessor)
            tx_obj.mint_amount = mint
            tx_obj.average_tx_size = self._average_amount()
            tx_obj.required_difficulty = len(self._current_prefix_for_level(tx_obj.level))

            # stats update (use post-mint amount)
            self.tx_counter += 1
            self.total_amount += amount

            self.mempool.append(tx_obj.__dict__)
            return tx_obj.__dict__

    def advance_b(self, my_index: int, target_index: int) -> Optional[Dict]:
        with self._lock:
            try:
                my_tx_dict = self.mempool[my_index]
                target_tx_dict = self.mempool[target_index]
            except IndexError:
                return None

            my_tx = TransactionBlock(**my_tx_dict)
            target_tx = TransactionBlock(**target_tx_dict)
            prefix = self._current_prefix_for_level(target_tx.level)
            ve.advance_to_state_b(my_tx, target_tx, prefix=prefix)
            # Auto-finalise the target transaction: move it to the blockchain
            # Fill balances before
            sender_before = self._balance_for(target_tx.sender_address)
            receiver_before = self._balance_for(target_tx.receiver_address)
            target_tx.sender_balance_before = sender_before
            target_tx.receiver_balance_before = receiver_before

            # Mine with current difficulty and set validator as my_tx sender
            start = time.time()
            ve.advance_to_state_c(target_tx, my_tx.sender_address, prefix=prefix)
            elapsed = time.time() - start

            # After inclusion, compute after balances
            minted = float(getattr(target_tx, "mint_amount", 0.0) or 0.0)
            debit = max(0.0, float(target_tx.amount) - max(0.0, minted))
            target_tx.sender_balance_after = sender_before - debit
            target_tx.receiver_balance_after = receiver_before + float(target_tx.amount)

            # Replace target in mempool with my_tx if indices collide after pop
            # First, commit target to blockchain and remove from mempool
            self.blockchain.append(target_tx.__dict__)
            self.mempool.pop(target_index)

            # Record timing and maybe retarget
            level = target_tx.level
            self._pow_durations_sec.setdefault(level, []).append(elapsed)
            self._c_blocks_since_retarget[level] = self._c_blocks_since_retarget.get(level, 0) + 1
            self._maybe_retarget(level)

            # Adjust my_index if it was after the popped target
            if my_index > target_index:
                my_index -= 1

            # Save back mutated my_tx at its (possibly shifted) index
            self.mempool[my_index] = my_tx.__dict__
            return my_tx.__dict__

    def advance_c(self, target_index: int, validator_address: str) -> Optional[Dict]:
        with self._lock:
            try:
                target_tx_dict = self.mempool[target_index]
            except IndexError:
                return None
            target_tx = TransactionBlock(**target_tx_dict)
            # Fill balances before
            sender_before = self._balance_for(target_tx.sender_address)
            receiver_before = self._balance_for(target_tx.receiver_address)
            target_tx.sender_balance_before = sender_before
            target_tx.receiver_balance_before = receiver_before

            # Mine with current difficulty
            prefix = self._current_prefix_for_level(target_tx.level)
            start = time.time()
            ve.advance_to_state_c(target_tx, validator_address, prefix=prefix)
            elapsed = time.time() - start

            # After inclusion, compute after balances
            minted = float(getattr(target_tx, "mint_amount", 0.0) or 0.0)
            debit = max(0.0, float(target_tx.amount) - max(0.0, minted))
            target_tx.sender_balance_after = sender_before - debit
            target_tx.receiver_balance_after = receiver_before + float(target_tx.amount)

            # Move from mempool to blockchain
            self.blockchain.append(target_tx.__dict__)
            self.mempool.pop(target_index)

            # Record timing and maybe retarget
            level = target_tx.level
            self._pow_durations_sec.setdefault(level, []).append(elapsed)
            self._c_blocks_since_retarget[level] = self._c_blocks_since_retarget.get(level, 0) + 1
            self._maybe_retarget(level)
            return target_tx.__dict__

    # ------------------------------------------------------------------
    # REST server convenience
    # ------------------------------------------------------------------
    def create_flask_app(self, import_name: str = "pasta_node_app") -> Flask:
        """Return a Flask app exposing the standard node JSON API."""
        from flask import Flask, jsonify, request  # local import to avoid mandatory dep
        from flask_cors import CORS

        app = Flask(import_name)
        CORS(app)

        # closure variables
        node = self

        @app.route("/blockchain")
        def _get_chain():
            return jsonify(node.get_blockchain())

        @app.route("/mempool")
        def _get_mempool():
            return jsonify(node.get_mempool())

        @app.route("/generate_keypair")
        def _gen_keypair():
            return jsonify(_generate_keypair())

        @app.route("/create_transaction", methods=["POST"])
        def _create_tx():
            data = request.get_json() or {}
            required = {"sender", "receiver", "amount"}
            if not required.issubset(set(data)):
                return "Missing fields", 400

            try:
                amount = float(data["amount"])
            except ValueError:
                return "Bad amount", 400

            tx = node.create_transaction(data["sender"], data["receiver"], amount)
            return jsonify({"message": "State A created", "tx": tx}), 201

        @app.route("/advance_b", methods=["POST"])
        def _advance_b():
            data = request.get_json() or {}
            required = {"my_index", "target_index"}
            if not required.issubset(set(data)):
                return "Missing fields", 400
            try:
                my_idx = int(data["my_index"])
                tgt_idx = int(data["target_index"])
            except ValueError:
                return "Index must be int", 400

            tx = node.advance_b(my_idx, tgt_idx)
            if tx is None:
                return "Bad indices", 400
            return jsonify({"message": "Advanced to B", "tx": tx})

        @app.route("/advance_c", methods=["POST"])
        def _advance_c():
            data = request.get_json() or {}
            required = {"target_index", "validator"}
            if not required.issubset(set(data)):
                return "Missing fields", 400
            try:
                tgt_idx = int(data["target_index"])
            except ValueError:
                return "Index must be int", 400
            tx = node.advance_c(tgt_idx, data["validator"])
            if tx is None:
                return "Bad index", 400
            return jsonify({"message": "Moved to blockchain", "tx": tx})

        return app

    def start_rest_server(self, host: str = "0.0.0.0", port: int = 5000, threaded: bool = True):
        """Convenience wrapper to run Flask dev server synchronously."""
        app = self.create_flask_app()
        app.run(host=host, port=port, threaded=threaded)


# -------------------------------------------------------------------------
# Convenience helpers at package level
# -------------------------------------------------------------------------

def create_default_app() -> "Flask":  # pragma: no cover – thin wrapper
    """Return a ready-to-run Flask app backed by a fresh in-memory Node."""
    node = Node()
    return node.create_flask_app()
