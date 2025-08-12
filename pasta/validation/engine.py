"""Simple validation engine implementing State A→B→C transitions with toy PoW.
This is NOT production secure—it is a functional prototype that follows the
spec at a very high level so front-end users can see state changes.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import asdict
from typing import Dict, Tuple, Optional

from pasta.core.models import TransactionBlock

# Default to no difficulty. Concrete prefixes should be provided by the caller.
DIFFICULTY_PREFIX = ""


def _hash_with_nonce(data: str, nonce: int) -> str:
    return hashlib.sha256(f"{data}{nonce}".encode()).hexdigest()


def mine_pow(block_dict: Dict, prefix: str = DIFFICULTY_PREFIX) -> Tuple[int, str]:
    """Very simple PoW: find nonce so hash(data+nonce) starts with prefix."""
    nonce = 0
    serialized = str(sorted(block_dict.items()))
    while True:
        h = _hash_with_nonce(serialized, nonce)
        if h.startswith(prefix):
            return nonce, h
        nonce += 1


# ------------------------------ API ---------------------------------------

def build_state_a(sender: str, receiver: str, amount: float, predecessor: TransactionBlock) -> TransactionBlock:
    """Create a new State-A transaction referencing predecessor block."""
    tx = TransactionBlock(
        sender_address=sender,
        receiver_address=receiver,
        amount=amount,
        timestamp=int(time.time()),
        predecessor_id=predecessor.block_hash,
        # Use the canonical content hash as predecessor_hash to distinguish
        # from the predecessor's final PoW block_hash/ID.
        predecessor_hash=predecessor.compute_hash(),
        level=predecessor.level,
        sender_balance_before=0,
        sender_balance_after=0,
        receiver_balance_before=0,
        receiver_balance_after=0,
        mint_amount=0,
        average_tx_size=0,
        required_difficulty=len(DIFFICULTY_PREFIX),
    )
    return tx


def advance_to_state_b(my_tx: TransactionBlock, target_tx: TransactionBlock, prefix: str = DIFFICULTY_PREFIX) -> None:
    """Perform validation PoW on target_tx, embed proof into my_tx."""
    nonce, h = mine_pow(asdict(target_tx), prefix=prefix)
    my_tx.validated_block_id = target_tx.block_hash or target_tx.compute_hash()
    my_tx.validated_block_hash = h
    # my_tx becomes State B (still waiting for validation)
    my_tx.state = "B"


def advance_to_state_c(target_tx: TransactionBlock, validator_address: str, prefix: str = DIFFICULTY_PREFIX) -> None:
    """Final validation of target_tx: we mine PoW for target itself."""
    nonce, h = mine_pow(asdict(target_tx), prefix=prefix)
    target_tx.validator_address = validator_address
    target_tx.nonce = nonce
    target_tx.block_hash = h
    # Now considered state C
    target_tx.state = "C"