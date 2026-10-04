"""The PaSta node: mempool, blockchain, protocol rules, optional persistence, REST app.

Every front-end (CLI, desktop GUI, REST server, tests) drives one :class:`Node`.
The node *enforces* the rules; :mod:`pasta.validation.engine` merely performs the
transitions. Rules enforced here (see ``docs/SPEC.md``):

* a transaction must carry a valid signature by its sender; nobody can send as GENESIS;
* amounts are whole base units (:mod:`pasta.core.units`);
* the sender must be able to cover ``amount`` from finalized balance minus pending spends;
* to reach State B a sender validates a *different* sender's State-B transaction;
* that target is finalized to State C with the validator recorded, then mined;
* every mutation is followed by a snapshot when ``storage_path`` is set.

Amount semantics: the sender pays ``amount``; the receiver is credited
``amount + mint_amount``. Coins enter the system two ways only: the genesis block credits
``genesis_receiver`` once, and the mint rule (:mod:`pasta.stability.chain`) sets
``mint_amount`` on every payment at the moment it is finalized.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional

from pasta.core.crypto import GENESIS_ADDRESS, compute_tx_id
from pasta.core.crypto import generate_keypair as _generate_keypair
from pasta.core.crypto import verify_transaction
from pasta.core.errors import (
    InsufficientBalance,
    InvalidSignature,
    InvalidTransaction,
    InvalidTransition,
    NotFound,
    PastaError,
)
from pasta.core.models import TransactionBlock
from pasta.core.units import UNITS_PER_PASTA, as_units, format_units
from pasta.stability.chain import LAUNCH_PARAMS, ChainStability, StabilityParams, replay
from pasta.validation import engine as ve
from pasta.validation.chain import verify_chain

__all__ = ["Node", "open_node", "create_default_app", "_generate_keypair"]

SNAPSHOT_VERSION = 2   # 2: integer base units, genesis credit, mint set at finalization


class Node:
    """In-memory blockchain node suitable for tests, REST, or GUI embedding."""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        *,
        genesis_receiver: Optional[str] = None,
        genesis_timestamp: Optional[int] = None,
        stability_params: StabilityParams = LAUNCH_PARAMS,
        require_signatures: bool = True,
        retarget_window: int = 2016,
        target_block_time: float = 600.0,
    ) -> None:
        self.storage_path = storage_path
        self.require_signatures = require_signatures
        self._lock = threading.RLock()

        self.blockchain: List[Dict[str, Any]] = []
        self.mempool: List[Dict[str, Any]] = []

        self.stability_params = stability_params
        self.stability = ChainStability(stability_params)

        # Difficulty management (per level), Bitcoin-style retarget
        self._retarget_window = int(retarget_window)
        self._target_block_time_l0 = float(target_block_time)
        self._difficulty_by_level: Dict[int, int] = {0: 0}
        self._pow_durations_sec: Dict[int, List[float]] = {0: []}
        self._c_blocks_since_retarget: Dict[int, int] = {0: 0}

        if storage_path and os.path.exists(storage_path):
            self._load()
        if not self.blockchain and not genesis_receiver:
            raise ValueError("a new chain needs genesis_receiver: the address credited with the genesis coins")
        if self.blockchain and genesis_receiver and genesis_receiver != self.genesis_receiver:
            raise ValueError("genesis_receiver does not match the stored chain")
        self._ensure_genesis(genesis_receiver, genesis_timestamp)
        self._save()

    @property
    def genesis_receiver(self) -> str:
        return self.blockchain[0]["receiver_address"] if self.blockchain else ""

    # ------------------------------------------------------------------
    # Genesis helpers
    # ------------------------------------------------------------------
    def _ensure_genesis(self, receiver: Optional[str], timestamp: Optional[int]) -> None:
        """Create the genesis block and a State-B bootstrap transaction to validate."""
        if not self.blockchain:
            genesis = TransactionBlock.create_genesis(
                receiver, self.stability_params.genesis_supply, timestamp).to_dict()
            self.blockchain.append(genesis)
            self.stability.apply(genesis)

        if not self.mempool and len(self.blockchain) == 1:
            genesis = self.blockchain[0]
            bootstrap = TransactionBlock(
                sender_address=GENESIS_ADDRESS,
                receiver_address=GENESIS_ADDRESS,
                amount=0,
                timestamp=int(genesis["timestamp"]) + 1,
                level=0,
                validated_block_id=genesis["tx_id"],
                validated_block_hash=genesis["block_hash"],
                state="B",
            )
            self.mempool.append(bootstrap.to_dict())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _snapshot(self) -> Dict[str, Any]:
        return {
            "version": SNAPSHOT_VERSION,
            "blockchain": self.blockchain,
            "mempool": self.mempool,
            "difficulty": {str(k): v for k, v in self._difficulty_by_level.items()},
        }

    def _save(self) -> None:
        if not self.storage_path:
            return
        directory = os.path.dirname(os.path.abspath(self.storage_path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".pasta-", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._snapshot(), fh, indent=1)
            os.replace(tmp, self.storage_path)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def _load(self) -> None:
        with open(self.storage_path, "r", encoding="utf-8") as fh:  # type: ignore[arg-type]
            data = json.load(fh)
        if int(data.get("version", 1)) != SNAPSHOT_VERSION:
            raise ValueError(
                f"{self.storage_path} was written by an older chain format "
                f"(version {data.get('version', 1)}, need {SNAPSHOT_VERSION}); start a new chain"
            )
        self.blockchain = list(data.get("blockchain", []))
        self.mempool = list(data.get("mempool", []))
        self.stability = replay(self.blockchain, self.stability_params)
        self._difficulty_by_level = {int(k): int(v) for k, v in data.get("difficulty", {"0": 0}).items()}
        for level in self._difficulty_by_level:
            self._pow_durations_sec.setdefault(level, [])
            self._c_blocks_since_retarget.setdefault(level, 0)

    # ------------------------------------------------------------------
    # Balances
    # ------------------------------------------------------------------
    def balance_for(self, address: str) -> int:
        """Finalized balance in base units: received (amount + mint) minus sent (amount)."""
        if not address or address == GENESIS_ADDRESS:
            return 0
        with self._lock:
            balance = 0
            for block in self.blockchain:
                if block.get("receiver_address") == address:
                    balance += int(block.get("amount", 0)) + int(block.get("mint_amount", 0))
                if block.get("sender_address") == address:
                    balance -= int(block.get("amount", 0))
            return balance

    def pending_outgoing(self, address: str) -> int:
        """Sum of amounts this address is already committed to spend in the mempool."""
        with self._lock:
            return sum(int(tx.get("amount", 0)) for tx in self.mempool if tx.get("sender_address") == address)

    # ------------------------------------------------------------------
    # Difficulty
    # ------------------------------------------------------------------
    def difficulty_for_level(self, level: int) -> int:
        return int(self._difficulty_by_level.get(level, 0))

    def _prefix_for_level(self, level: int) -> str:
        return "0" * max(0, self.difficulty_for_level(level))

    def _target_block_time_for_level(self, level: int) -> float:
        return max(1.0, self._target_block_time_l0 / (2 ** max(0, int(level))))

    def _record_block_time(self, level: int, elapsed: float) -> None:
        self._pow_durations_sec.setdefault(level, []).append(float(elapsed))
        self._c_blocks_since_retarget[level] = self._c_blocks_since_retarget.get(level, 0) + 1
        self._maybe_retarget(level)

    def _maybe_retarget(self, level: int) -> None:
        if self._c_blocks_since_retarget.get(level, 0) < self._retarget_window:
            return
        times = self._pow_durations_sec.get(level, [])
        self._c_blocks_since_retarget[level] = 0
        self._pow_durations_sec[level] = []
        if not times:
            return
        avg_time = sum(times) / len(times)
        target = self._target_block_time_for_level(level)
        current = self._difficulty_by_level.get(level, 0)
        if avg_time < target:
            self._difficulty_by_level[level] = current + 1
        elif avg_time > target and current > 0:
            self._difficulty_by_level[level] = current - 1

    # ------------------------------------------------------------------
    # Queries (thread-safe copies)
    # ------------------------------------------------------------------
    def get_blockchain(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(b) for b in self.blockchain]

    def get_mempool(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(t) for t in self.mempool]

    def get_mempool_tx(self, tx_id: str) -> Dict[str, Any]:
        with self._lock:
            return dict(self.mempool[self._mempool_index(tx_id)])

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "height": len(self.blockchain),
                "mempool_size": len(self.mempool),
                "units_per_pasta": UNITS_PER_PASTA,
                "genesis_receiver": self.genesis_receiver,
                "stability": self.stability.status(),
                "difficulty": {str(k): v for k, v in self._difficulty_by_level.items()},
                "require_signatures": self.require_signatures,
                "persistent": bool(self.storage_path),
            }

    def verify(self) -> List[str]:
        """Re-validate the whole chain from scratch. Empty list means consistent."""
        return verify_chain(self.get_blockchain(), self.stability_params)

    def _mempool_index(self, tx_id: str) -> int:
        for i, tx in enumerate(self.mempool):
            if tx.get("tx_id") == tx_id:
                return i
        raise NotFound(f"transaction {tx_id[:12]}... is not in the mempool")

    def _known_tx_ids(self) -> set:
        return {b.get("tx_id") for b in self.blockchain} | {t.get("tx_id") for t in self.mempool}

    # ------------------------------------------------------------------
    # Transaction workflow
    # ------------------------------------------------------------------
    def create_transaction(
        self,
        sender: str,
        receiver: str,
        amount: int,
        timestamp: Optional[int] = None,
        signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate and admit a State-A transaction to the mempool. ``amount`` is in base units.

        Raises :class:`PastaError` subclasses on rejection.
        """
        if not sender or not receiver:
            raise InvalidTransaction("sender and receiver are required")
        if sender == GENESIS_ADDRESS:
            raise InvalidTransaction("nobody can send as GENESIS")
        try:
            amount = as_units(amount)
        except ValueError as exc:
            raise InvalidTransaction(str(exc)) from None
        if amount < 0:
            raise InvalidTransaction("amount must be non-negative")
        if amount > 0 and sender == receiver:
            raise InvalidTransaction("sender and receiver must differ (only a zero-amount transaction may be sent to yourself)")
        timestamp = int(timestamp if timestamp is not None else time.time())

        if self.require_signatures:
            if not verify_transaction(sender, receiver, amount, timestamp, signature):
                raise InvalidSignature("signature missing or invalid for sender")

        with self._lock:
            tx_id = compute_tx_id(sender, receiver, amount, timestamp)
            if tx_id in self._known_tx_ids():
                raise InvalidTransaction("duplicate transaction (same sender, receiver, amount, timestamp)")

            available = self.balance_for(sender) - self.pending_outgoing(sender)
            if available < amount:
                raise InsufficientBalance(
                    f"sender has {format_units(available)} PASTA available, needs {format_units(amount)}"
                )

            tx = ve.build_state_a(
                sender,
                receiver,
                amount,
                timestamp,
                signature,
                level=int(self.blockchain[-1].get("level", 0)),
            )
            tx.required_difficulty = self.difficulty_for_level(tx.level)

            self.mempool.append(tx.to_dict())
            self._save()
            return tx.to_dict()

    def validate(self, my_tx_id: str, target_tx_id: str) -> Dict[str, Any]:
        """State A -> B for ``my_tx`` by finalizing ``target`` (State B -> C).

        Returns ``{"my_tx": ..., "finalized": ...}``. Raises :class:`PastaError` subclasses.
        """
        with self._lock:
            my_idx = self._mempool_index(my_tx_id)
            target_idx = self._mempool_index(target_tx_id)
            my_tx = TransactionBlock.from_dict(self.mempool[my_idx])
            target = TransactionBlock.from_dict(self.mempool[target_idx])

            if my_tx.tx_id == target.tx_id:
                raise InvalidTransition("a transaction cannot validate itself")
            if my_tx.state != "A":
                raise InvalidTransition(f"your transaction is in state {my_tx.state}, only state A can validate")
            if target.state != "B":
                raise InvalidTransition(f"target is in state {target.state}; only state B transactions are eligible")
            if target.sender_address == my_tx.sender_address:
                raise InvalidTransition("self-validation: target has the same sender as your transaction")

            sender_before = self.balance_for(target.sender_address)
            receiver_before = self.balance_for(target.receiver_address)
            if not target.is_genesis_sender() and sender_before < target.amount:
                # The target can never be finalized; drop it so the mempool does not rot.
                self.mempool.pop(target_idx)
                self._save()
                raise InsufficientBalance(
                    f"target sender has {format_units(sender_before)} PASTA, "
                    f"needs {format_units(target.amount)}; target dropped"
                )

            predecessor = TransactionBlock.from_dict(self.blockchain[-1])
            prefix = self._prefix_for_level(target.level)
            started = time.time()
            ve.finalize_block(
                target,
                validator_address=my_tx.sender_address,
                predecessor=predecessor,
                prefix=prefix,
                sender_balance_before=sender_before,
                receiver_balance_before=receiver_before,
                # the mint rule is a function of the chain so far; verify_chain recomputes both
                mint_amount=self.stability.mint_for(target.sender_address, target.receiver_address, target.amount),
                average_tx_size=self.stability.smoothed_median(),
            )
            elapsed = time.time() - started

            self.blockchain.append(target.to_dict())
            self.stability.apply(self.blockchain[-1])
            self.mempool.pop(target_idx)
            if my_idx > target_idx:
                my_idx -= 1

            ve.attach_validation_proof(my_tx, target)
            self.mempool[my_idx] = my_tx.to_dict()

            self._record_block_time(target.level, elapsed)
            self._save()
            return {"my_tx": my_tx.to_dict(), "finalized": target.to_dict()}

    # ------------------------------------------------------------------
    # REST server
    # ------------------------------------------------------------------
    def create_flask_app(self, import_name: str = "pasta_node_app"):
        """Return a Flask app exposing the node JSON API."""
        from flask import Flask, jsonify, request
        from flask_cors import CORS

        app = Flask(import_name)
        CORS(app)
        node = self

        @app.errorhandler(PastaError)
        def _pasta_error(exc):
            return jsonify({"error": str(exc), "type": type(exc).__name__}), 400

        @app.route("/status")
        def _status():
            return jsonify(node.status())

        @app.route("/blockchain")
        def _get_chain():
            return jsonify(node.get_blockchain())

        @app.route("/mempool")
        def _get_mempool():
            return jsonify(node.get_mempool())

        @app.route("/mempool/<tx_id>")
        def _get_mempool_tx(tx_id: str):
            return jsonify(node.get_mempool_tx(tx_id))

        @app.route("/balance/<address>")
        def _balance(address: str):
            return jsonify({
                "address": address,
                "balance": node.balance_for(address),
                "pending_outgoing": node.pending_outgoing(address),
            })

        @app.route("/verify")
        def _verify():
            problems = node.verify()
            return jsonify({"ok": not problems, "problems": problems})

        @app.route("/generate_keypair")
        def _gen_keypair():
            return jsonify(_generate_keypair())

        @app.route("/create_transaction", methods=["POST"])
        def _create_tx():
            data = request.get_json(silent=True) or {}
            missing = {"sender", "receiver", "amount"} - set(data)
            if missing:
                return jsonify({"error": f"missing fields: {sorted(missing)}"}), 400
            tx = node.create_transaction(
                data["sender"], data["receiver"], data["amount"],
                timestamp=data.get("timestamp"), signature=data.get("signature"),
            )
            return jsonify({"message": "State A created", "tx": tx}), 201

        @app.route("/validate", methods=["POST"])
        def _validate():
            data = request.get_json(silent=True) or {}
            missing = {"my_tx_id", "target_tx_id"} - set(data)
            if missing:
                return jsonify({"error": f"missing fields: {sorted(missing)}"}), 400
            result = node.validate(str(data["my_tx_id"]), str(data["target_tx_id"]))
            return jsonify({"message": "Your transaction is in State B; target finalized", **result})

        @app.route("/advance_b", methods=["POST"])
        @app.route("/advance_c", methods=["POST"])
        def _gone():
            return jsonify({"error": "removed in 0.2.0; use POST /validate with my_tx_id and target_tx_id"}), 410

        return app

    def start_rest_server(self, host: str = "0.0.0.0", port: int = 5000, threaded: bool = True):
        """Run the Flask development server synchronously."""
        self.create_flask_app().run(host=host, port=port, threaded=threaded)


def open_node(storage_path: Optional[str] = None, genesis_receiver: Optional[str] = None, **kwargs):
    """Open the chain stored at ``storage_path``, or start a new one.

    A new chain needs an address to credit with the genesis coins. When none is given a
    fresh keypair is generated and returned, so the caller can show or save it; that key
    then holds every coin in existence. Returns ``(node, new_keypair_or_None)``.
    """
    new_chain = not (storage_path and os.path.exists(storage_path))
    keypair = None
    if new_chain and not genesis_receiver:
        keypair = _generate_keypair()
        genesis_receiver = keypair["public_key"]
    node = Node(storage_path, genesis_receiver=genesis_receiver if new_chain else None, **kwargs)
    return node, keypair


def create_default_app():  # pragma: no cover - thin wrapper
    """Flask app for WSGI servers: chain from ``PASTA_STORAGE``, and for a new chain the
    genesis address from ``PASTA_GENESIS_ADDRESS`` (required)."""
    storage = os.getenv("PASTA_STORAGE") or None
    return Node(storage, genesis_receiver=os.getenv("PASTA_GENESIS_ADDRESS") or None).create_flask_app()
