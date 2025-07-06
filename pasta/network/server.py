"""Flask REST server for Pasta prototype (refactored)."""
from __future__ import annotations

import os, threading, json, time, argparse
from flask import Flask, request, jsonify
from flask_cors import CORS

from pasta.core.models import TransactionBlock
from pasta.validation import engine as ve
from pasta.core.crypto import generate_keypair as _gen_kp

app = Flask(__name__)
CORS(app)

# Simple in-memory state (prototype)
BLOCKCHAIN: list[dict] = []
MEMPOOL: list[dict] = []
LOCK = threading.Lock()

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def ensure_genesis():
    if not BLOCKCHAIN:
        gen = TransactionBlock.create_genesis()
        BLOCKCHAIN.append(gen.__dict__)

ensure_genesis()

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.route("/blockchain")
def get_chain():
    with LOCK:
        return jsonify(BLOCKCHAIN)

@app.route("/mempool")
def get_mempool():
    with LOCK:
        return jsonify(MEMPOOL)

@app.route("/generate_keypair")
def gen_keypair():
    return jsonify(_gen_kp())

@app.route("/create_transaction", methods=["POST"])
def create_tx():
    data = request.get_json() or {}
    required = {"sender", "receiver", "amount"}
    if not required.issubset(set(data)):
        return "Missing fields", 400

    amount = float(data["amount"])
    with LOCK:
        predecessor_dict = BLOCKCHAIN[-1]
        predecessor = TransactionBlock(**predecessor_dict)
        tx_obj = ve.build_state_a(data["sender"], data["receiver"], amount, predecessor)
        MEMPOOL.append(tx_obj.__dict__)

    return jsonify({"message": "State A created", "tx": tx_obj.__dict__}), 201

# --- State B route ---

@app.route("/advance_b", methods=["POST"])
def advance_b():
    data = request.get_json() or {}
    required = {"my_index", "target_index"}
    if not required.issubset(set(data)):
        return "Missing fields", 400
    with LOCK:
        try:
            my_tx_dict = MEMPOOL[int(data["my_index"])]
            target_tx_dict = MEMPOOL[int(data["target_index"])]
        except (IndexError, ValueError):
            return "Bad indices", 400

        my_tx = TransactionBlock(**my_tx_dict)
        target_tx = TransactionBlock(**target_tx_dict)
        ve.advance_to_state_b(my_tx, target_tx)
        MEMPOOL[int(data["my_index"])] = my_tx.__dict__
        return jsonify({"message": "Advanced to B", "tx": my_tx.__dict__})

# --- State C route ---

@app.route("/advance_c", methods=["POST"])
def advance_c():
    data = request.get_json() or {}
    required = {"target_index", "validator"}
    if not required.issubset(set(data)):
        return "Missing fields", 400
    with LOCK:
        try:
            target_tx_dict = MEMPOOL[int(data["target_index"])]
        except (IndexError, ValueError):
            return "Bad index", 400
        target_tx = TransactionBlock(**target_tx_dict)
        ve.advance_to_state_c(target_tx, data["validator"])
        BLOCKCHAIN.append(target_tx.__dict__)
        MEMPOOL.pop(int(data["target_index"]))
    return jsonify({"message": "Moved to blockchain", "tx": target_tx.__dict__})

# ------------------------------------------------------------------
# WSGI entry (Gunicorn)
# ------------------------------------------------------------------

def run():
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    run() 