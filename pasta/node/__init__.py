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
    def create_transaction(self, sender: str, receiver: str, amount: float) -> Dict:
        """Create a State-A transaction and add it to mempool."""
        with self._lock:
            predecessor_dict = self.blockchain[-1]
            predecessor = TransactionBlock(**predecessor_dict)
            tx_obj = ve.build_state_a(sender, receiver, amount, predecessor)
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
            ve.advance_to_state_b(my_tx, target_tx)
            # Save back mutated my_tx
            self.mempool[my_index] = my_tx.__dict__
            return my_tx.__dict__

    def advance_c(self, target_index: int, validator_address: str) -> Optional[Dict]:
        with self._lock:
            try:
                target_tx_dict = self.mempool[target_index]
            except IndexError:
                return None
            target_tx = TransactionBlock(**target_tx_dict)
            ve.advance_to_state_c(target_tx, validator_address)
            # Move from mempool to blockchain
            self.blockchain.append(target_tx.__dict__)
            self.mempool.pop(target_index)
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
