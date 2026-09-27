"""The one block type of the prototype: a single transaction.

Life-cycle (see ``docs/SPEC.md``):

* **State A** - created and signed by the sender, sitting in the mempool.
* **State B** - the sender has validated *another* State-B transaction; proof of that
  work is embedded in ``validated_block_id`` / ``validated_block_hash``. Now eligible.
* **State C** - finalized by a validator who is not the sender: linked to a predecessor,
  balances filled in, proof-of-work mined, appended to the chain.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, fields
from typing import Any, Optional

from pasta.core.crypto import GENESIS_ADDRESS, compute_tx_id


@dataclass
class TransactionBlock:
    # Signed transaction data (covered by tx_id and signature)
    sender_address: str
    receiver_address: str
    amount: float
    timestamp: int

    # Blockchain linkage (set at finalization)
    predecessor_id: str = ""
    predecessor_hash: str = ""
    level: int = 0

    # Balance information (set at finalization)
    sender_balance_before: float = 0.0
    sender_balance_after: float = 0.0
    receiver_balance_before: float = 0.0
    receiver_balance_after: float = 0.0

    # Stability mechanism. Receiver is credited amount + mint_amount; sender pays amount.
    mint_amount: float = 0.0  # positive = mint, negative = burn
    average_tx_size: float = 0.0

    # Validation requirements
    required_difficulty: int = 0
    storage_requirement: int = 0

    # Proof that this transaction's sender validated another block (State B)
    validated_block_id: Optional[str] = None
    validated_block_hash: Optional[str] = None

    # Final validation (State C)
    validator_address: Optional[str] = None
    block_hash: Optional[str] = None
    nonce: Optional[int] = None

    # State marker: "A", "B" or "C"
    state: str = "A"

    # Sender's signature over the canonical payload (Base58). None only for GENESIS.
    signature: Optional[str] = None

    # Stable identity: sha256(canonical payload). Filled by __post_init__ when empty.
    tx_id: str = ""

    def __post_init__(self) -> None:
        if not self.tx_id:
            self.tx_id = compute_tx_id(self.sender_address, self.receiver_address, self.amount, self.timestamp)

    # ------------------------------------------------------------------ helpers

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransactionBlock":
        """Build from a dict, ignoring unknown keys (forward/backward compatibility)."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_genesis_sender(self) -> bool:
        return self.sender_address == GENESIS_ADDRESS

    def compute_hash(self) -> str:
        """Content hash over every field except ``block_hash`` and ``nonce``."""
        data = asdict(self)
        data.pop("block_hash", None)
        data.pop("nonce", None)
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    @classmethod
    def create_genesis(cls, timestamp: Optional[int] = None) -> "TransactionBlock":
        """The first block. No signature, no PoW; its hash is its content hash."""
        genesis = cls(
            sender_address=GENESIS_ADDRESS,
            receiver_address=GENESIS_ADDRESS,
            amount=0.0,
            timestamp=int(timestamp if timestamp is not None else time.time()),
            predecessor_id=GENESIS_ADDRESS,
            predecessor_hash="0",
            level=0,
            validator_address=GENESIS_ADDRESS,
            state="C",
        )
        genesis.block_hash = genesis.compute_hash()
        return genesis
