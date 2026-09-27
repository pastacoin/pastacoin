"""Independent re-validation of a whole chain.

:func:`verify_chain` takes the list of block dicts a node would return from
``GET /blockchain`` and returns a list of human-readable problems. An empty list means
the chain is internally consistent: hash links, proof-of-work, signatures, validator
rule, balances and transaction ids all check out. It relies on nothing but the chain
itself, so a peer can run it on a chain it just downloaded.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List

from pasta.core.crypto import GENESIS_ADDRESS, compute_tx_id, verify_transaction
from pasta.core.models import TransactionBlock
from pasta.validation.engine import pow_is_valid

_TOL = 1e-9


def _close(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), abs_tol=_TOL)


def verify_chain(chain: List[Dict[str, Any]]) -> List[str]:
    problems: List[str] = []
    if not chain:
        return ["chain is empty"]

    # ---- genesis
    g = chain[0]
    if g.get("sender_address") != GENESIS_ADDRESS or g.get("receiver_address") != GENESIS_ADDRESS:
        problems.append("block 0: genesis must be GENESIS -> GENESIS")
    if g.get("predecessor_id") != GENESIS_ADDRESS:
        problems.append("block 0: genesis predecessor_id must be GENESIS")
    if g.get("state") != "C":
        problems.append("block 0: genesis must be in state C")
    try:
        if TransactionBlock.from_dict(g).compute_hash() != g.get("block_hash"):
            problems.append("block 0: genesis block_hash does not match content")
    except TypeError as exc:
        problems.append(f"block 0: malformed genesis ({exc})")
        return problems

    balances: Dict[str, float] = defaultdict(float)
    seen_ids = {g.get("tx_id")}

    for i in range(1, len(chain)):
        b = chain[i]
        prev = chain[i - 1]
        tag = f"block {i}"
        sender = b.get("sender_address", "")
        receiver = b.get("receiver_address", "")
        amount = float(b.get("amount", 0.0))
        mint = float(b.get("mint_amount", 0.0))

        # identity
        expected_id = compute_tx_id(sender, receiver, amount, int(b.get("timestamp", 0)))
        if b.get("tx_id") != expected_id:
            problems.append(f"{tag}: tx_id does not match canonical payload")
        if b.get("tx_id") in seen_ids:
            problems.append(f"{tag}: duplicate tx_id {str(b.get('tx_id'))[:12]}")
        seen_ids.add(b.get("tx_id"))

        # linkage
        if b.get("predecessor_hash") != prev.get("block_hash"):
            problems.append(f"{tag}: predecessor_hash does not match block {i - 1}")
        if b.get("predecessor_id") != prev.get("block_hash"):
            problems.append(f"{tag}: predecessor_id does not match block {i - 1}")

        # state machine
        if b.get("state") != "C":
            problems.append(f"{tag}: on-chain block must be in state C (is {b.get('state')!r})")
        validator = b.get("validator_address")
        if not validator:
            problems.append(f"{tag}: missing validator_address")
        elif validator == sender:
            problems.append(f"{tag}: self-validation (validator equals sender)")

        # signature
        if sender != GENESIS_ADDRESS:
            if not verify_transaction(sender, receiver, amount, int(b.get("timestamp", 0)), b.get("signature")):
                problems.append(f"{tag}: bad or missing signature")

        # proof of work
        prefix = "0" * int(b.get("required_difficulty", 0) or 0)
        if not pow_is_valid(b, prefix):
            problems.append(f"{tag}: proof-of-work invalid")

        # balances
        if amount < 0:
            problems.append(f"{tag}: negative amount")
        if sender != GENESIS_ADDRESS:
            if not _close(b.get("sender_balance_before", 0.0), balances[sender]):
                problems.append(f"{tag}: sender_balance_before {b.get('sender_balance_before')} != running {balances[sender]}")
            if balances[sender] + _TOL < amount:
                problems.append(f"{tag}: overdraft (balance {balances[sender]}, amount {amount})")
        if not _close(b.get("receiver_balance_before", 0.0), balances[receiver]):
            problems.append(f"{tag}: receiver_balance_before {b.get('receiver_balance_before')} != running {balances[receiver]}")

        if sender != GENESIS_ADDRESS:
            balances[sender] -= amount
        balances[receiver] += amount + mint

        if sender != GENESIS_ADDRESS and not _close(b.get("sender_balance_after", 0.0), balances[sender]):
            problems.append(f"{tag}: sender_balance_after inconsistent")
        if not _close(b.get("receiver_balance_after", 0.0), balances[receiver]):
            problems.append(f"{tag}: receiver_balance_after inconsistent")

    return problems
