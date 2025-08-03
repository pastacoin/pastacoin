from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

@dataclass
class TransactionBlock:
    # Transaction Data
    sender_address: str
    receiver_address: str
    amount: float
    timestamp: int

    # Blockchain linkage
    predecessor_id: str
    predecessor_hash: str
    level: int = 0

    # Balance information
    sender_balance_before: float = 0.0
    sender_balance_after: float = 0.0
    receiver_balance_before: float = 0.0
    receiver_balance_after: float = 0.0

    # Stability mechanism
    mint_amount: float = 0.0  # positive=mint, negative=burn
    average_tx_size: float = 0.0

    # Validation requirements
    required_difficulty: int = 1
    storage_requirement: int = 0

    # Validation proof (state B)
    validated_block_id: Optional[str] = None
    validated_block_hash: Optional[str] = None

    # Final validation (state C)
    validator_address: Optional[str] = None
    block_hash: Optional[str] = None
    nonce: Optional[int] = None

    # State marker (A, B, C) simple prototype indicator
    state: str = "A"

    # Extra: signature (not in original spec block but necessary)
    signature: Optional[str] = None

    def compute_hash(self) -> str:
        data = asdict(self).copy()
        data.pop("block_hash", None)
        data.pop("nonce", None)
        serialized = str(sorted(data.items())).encode()
        return hashlib.sha256(serialized).hexdigest()

    @classmethod
    def create_genesis(cls) -> "TransactionBlock":
        timestamp = int(time.time())
        genesis = cls(
            sender_address="GENESIS",
            receiver_address="GENESIS",
            amount=0,
            timestamp=timestamp,
            predecessor_id="GENESIS",
            predecessor_hash="0",
            level=0,
        )
        genesis.block_hash = genesis.compute_hash()
        return genesis 