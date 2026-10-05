"""State A -> B -> C transitions and the toy proof-of-work.

This module is pure: it mutates the ``TransactionBlock`` objects it is handed and never
touches node state, balances policy or the network. The :class:`pasta.node.Node`
decides *whether* a transition is allowed; this module performs it.

Proof-of-work: ``sha256(serialize(block) + str(nonce))`` must start with ``prefix``
(``"0" * required_difficulty``). ``serialize`` is the block dict with ``block_hash`` and
``nonce`` blanked, rendered as JSON with sorted keys, so every other field - including
validator, state, predecessor and balances - is covered by the proof.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Tuple

from pasta.core.models import TransactionBlock


# ----------------------------------------------------------------- PoW ----

def serialize_for_pow(block: Dict[str, Any]) -> str:
    data = dict(block)
    data["block_hash"] = None
    data["nonce"] = None
    return json.dumps(data, sort_keys=True)


def pow_hash(serialized: str, nonce: int) -> str:
    return hashlib.sha256(f"{serialized}{nonce}".encode()).hexdigest()


def mine_pow(block: Dict[str, Any], prefix: str = "") -> Tuple[int, str]:
    """Find the smallest nonce whose hash starts with ``prefix``."""
    serialized = serialize_for_pow(block)
    nonce = 0
    while True:
        h = pow_hash(serialized, nonce)
        if h.startswith(prefix):
            return nonce, h
        nonce += 1


def pow_is_valid(block: Dict[str, Any], prefix: str) -> bool:
    """Recompute the PoW hash of a finalized block dict and compare."""
    nonce = block.get("nonce")
    block_hash = block.get("block_hash")
    if nonce is None or not block_hash:
        return False
    return pow_hash(serialize_for_pow(block), int(nonce)) == block_hash and block_hash.startswith(prefix)


# --------------------------------------------------------- transitions ----

def build_state_a(
    sender: str,
    receiver: str,
    amount: int,
    timestamp: int,
    signature: str | None,
    *,
    level: int = 0,
) -> TransactionBlock:
    """Create a new State-A transaction. Linkage, balances and mint are filled at finalization."""
    return TransactionBlock(
        sender_address=sender,
        receiver_address=receiver,
        amount=int(amount),
        timestamp=int(timestamp),
        level=level,
        signature=signature,
        state="A",
    )


def finalize_block(
    target: TransactionBlock,
    *,
    validator_address: str,
    predecessor: TransactionBlock,
    prefix: str,
    sender_balance_before: int,
    receiver_balance_before: int,
    mint_amount: int = 0,
    average_tx_size: int = 0,
) -> None:
    """State B -> C: link, fill balances and mint, mark validator, mine. Mutates ``target``."""
    target.mint_amount = int(mint_amount)
    target.average_tx_size = int(average_tx_size)
    target.predecessor_id = predecessor.block_hash or ""
    target.predecessor_hash = predecessor.block_hash or ""
    target.level = predecessor.level
    target.validator_address = validator_address
    target.required_difficulty = len(prefix)
    target.sender_balance_before = sender_balance_before
    target.receiver_balance_before = receiver_balance_before
    if target.is_genesis_sender():
        target.sender_balance_after = sender_balance_before
    else:
        target.sender_balance_after = sender_balance_before - target.amount
    target.receiver_balance_after = receiver_balance_before + target.amount + target.mint_amount
    target.state = "C"
    target.block_hash = None
    target.nonce = None
    nonce, h = mine_pow(target.to_dict(), prefix=prefix)
    target.nonce = nonce
    target.block_hash = h


def attach_validation_proof(my_tx: TransactionBlock, finalized_target: TransactionBlock) -> None:
    """State A -> B: record that ``my_tx``'s sender finalized ``finalized_target``."""
    my_tx.validated_block_id = finalized_target.tx_id
    my_tx.validated_block_hash = finalized_target.block_hash
    my_tx.state = "B"
