"""Independent re-validation of a chain.

:func:`verify_chain` takes the list of block dicts a node would return from
``GET /blockchain`` and returns a list of human-readable problems. An empty list means
the chain is internally consistent: genesis credit, hash links, proof-of-work, signatures,
validator rule, balances, transaction ids and every mint or burn all check out. It relies on
nothing but the chain itself, so a peer can run it on a chain it just downloaded.

:class:`ChainVerifier` is the same check one block at a time. A node that follows another
(:mod:`pasta.node.replica`) keeps one and feeds it each new block, so following a long chain
does not mean re-checking all of it for every block.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from pasta.core.crypto import GENESIS_ADDRESS, compute_tx_id, verify_transaction
from pasta.core.models import TransactionBlock
from pasta.stability.chain import LAUNCH_PARAMS, ChainStability, StabilityParams
from pasta.validation.engine import pow_is_valid


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


class ChainVerifier:
    """Checks blocks in chain order and keeps the state the checks need.

    ``check(block)`` reports what is wrong with ``block`` as the next block; ``apply(block)``
    moves past it. ``balances`` and ``stability`` are therefore the verified state of
    everything applied so far.
    """

    def __init__(self, params: StabilityParams = LAUNCH_PARAMS) -> None:
        self.params = params
        self.height = 0
        self.tip: Optional[Dict[str, Any]] = None
        self.balances: Dict[str, int] = defaultdict(int)
        self.seen_ids: set = set()
        self.stability = ChainStability(params)

    # ------------------------------------------------------------------ checks
    def check(self, block: Dict[str, Any]) -> List[str]:
        return self._check_genesis(block) if self.height == 0 else self._check_next(block)

    def _check_genesis(self, g: Dict[str, Any]) -> List[str]:
        problems: List[str] = []
        if g.get("sender_address") != GENESIS_ADDRESS:
            problems.append("block 0: genesis sender must be GENESIS")
        if not g.get("receiver_address") or g.get("receiver_address") == GENESIS_ADDRESS:
            problems.append("block 0: genesis must credit a real address")
        if g.get("amount") != self.params.genesis_supply or not _is_int(g.get("amount")):
            problems.append(f"block 0: genesis amount must be {self.params.genesis_supply} base units")
        if g.get("mint_amount", 0) != 0:
            problems.append("block 0: genesis carries no mint")
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

    def _check_next(self, b: Dict[str, Any]) -> List[str]:
        problems: List[str] = []
        i = self.height
        prev = self.tip or {}
        tag = f"block {i}"
        sender = b.get("sender_address", "")
        receiver = b.get("receiver_address", "")
        amount = b.get("amount", 0)
        mint = b.get("mint_amount", 0)
        if not _is_int(amount) or not _is_int(mint):
            return [f"{tag}: amount and mint_amount must be whole base units"]

        # identity
        expected_id = compute_tx_id(sender, receiver, amount, int(b.get("timestamp", 0)))
        if b.get("tx_id") != expected_id:
            problems.append(f"{tag}: tx_id does not match canonical payload")
        if b.get("tx_id") in self.seen_ids:
            problems.append(f"{tag}: duplicate tx_id {str(b.get('tx_id'))[:12]}")

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

        # signature; after block 0, GENESIS may only appear as the empty bootstrap block
        if sender == GENESIS_ADDRESS:
            if amount != 0 or receiver != GENESIS_ADDRESS:
                problems.append(f"{tag}: GENESIS can send nothing after block 0")
        elif not verify_transaction(sender, receiver, amount, int(b.get("timestamp", 0)), b.get("signature")):
            problems.append(f"{tag}: bad or missing signature")

        # proof of work
        prefix = "0" * int(b.get("required_difficulty", 0) or 0)
        if not pow_is_valid(b, prefix):
            problems.append(f"{tag}: proof-of-work invalid")

        # amounts
        if amount < 0:
            problems.append(f"{tag}: negative amount")
        if amount > 0 and sender == receiver:
            problems.append(f"{tag}: self-payment with a non-zero amount")

        # mint rule: must equal what the rule yields for the chain so far
        expected_mint = self.stability.mint_for(sender, receiver, amount)
        if mint != expected_mint:
            problems.append(f"{tag}: mint_amount {mint} != rule {expected_mint}")
        if b.get("average_tx_size", 0) != self.stability.smoothed_median():
            problems.append(f"{tag}: average_tx_size does not match the rule's smoothed median")

        # balances
        bal = self.balances
        if sender != GENESIS_ADDRESS:
            if b.get("sender_balance_before", 0) != bal[sender]:
                problems.append(f"{tag}: sender_balance_before {b.get('sender_balance_before')} != running {bal[sender]}")
            if bal[sender] < amount:
                problems.append(f"{tag}: overdraft (balance {bal[sender]}, amount {amount})")
        if b.get("receiver_balance_before", 0) != bal[receiver]:
            problems.append(f"{tag}: receiver_balance_before {b.get('receiver_balance_before')} != running {bal[receiver]}")
        sender_after = bal[sender] - amount if sender != GENESIS_ADDRESS else 0
        receiver_after = (sender_after if receiver == sender else bal[receiver]) + amount + mint
        if sender != GENESIS_ADDRESS and receiver != sender and b.get("sender_balance_after", 0) != sender_after:
            problems.append(f"{tag}: sender_balance_after inconsistent")
        if b.get("receiver_balance_after", 0) != receiver_after:
            problems.append(f"{tag}: receiver_balance_after inconsistent")
        return problems

    # ------------------------------------------------------------------ advance
    def apply(self, block: Dict[str, Any]) -> None:
        """Move past ``block`` (normally only after ``check`` returned nothing)."""
        sender = block.get("sender_address", "")
        receiver = block.get("receiver_address", "")
        amount = block.get("amount", 0) if _is_int(block.get("amount", 0)) else 0
        mint = block.get("mint_amount", 0) if _is_int(block.get("mint_amount", 0)) else 0
        if sender != GENESIS_ADDRESS:
            self.balances[sender] -= amount
        self.balances[receiver] += amount + mint
        self.seen_ids.add(block.get("tx_id"))
        self.stability.apply({**block, "amount": amount, "mint_amount": mint})
        self.tip = block
        self.height += 1

    def add(self, block: Dict[str, Any]) -> List[str]:
        """Check and, if clean, apply. Returns the problems (empty when the block was accepted)."""
        problems = self.check(block)
        if not problems:
            self.apply(block)
        return problems


def verify_chain(chain: List[Dict[str, Any]], params: StabilityParams = LAUNCH_PARAMS) -> List[str]:
    if not chain:
        return ["chain is empty"]
    verifier = ChainVerifier(params)
    problems: List[str] = []
    for block in chain:
        found = verifier.check(block)
        problems.extend(found)
        if any("malformed genesis" in p or "must be whole base units" in p for p in found):
            return problems
        verifier.apply(block)
    return problems
