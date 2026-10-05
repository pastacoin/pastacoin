"""Wallets and the payment flows every front-end shares.

A wallet is a named keypair. :class:`WalletStore` keeps them in one JSON file on the user's
own computer. **The file is not encrypted**: this is a prototype for a coin with no value,
and anyone who can read the file can spend from its wallets.

:func:`send_payment` and :func:`confirm` are the two things a person does:

* *send*: sign a payment, post it, and immediately validate another waiting transaction so
  the payment becomes eligible (State B);
* *confirm*: finalize somebody else's waiting transaction (State B to C) by posting a
  zero-amount transaction of one's own and validating the target with it.

``backend`` is a :class:`pasta.node.Node` or a :class:`pasta.node.replica.Replica`.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from pasta.core.crypto import compute_tx_id, generate_keypair, public_key_for, sign_transaction
from pasta.core.errors import InvalidTransaction, PastaError


@dataclass
class Wallet:
    name: str
    private_key: str
    public_key: str

    @property
    def address(self) -> str:
        return self.public_key


class WalletStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self.wallets: List[Wallet] = []
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.wallets = [Wallet(w["name"], w["private_key"], w["public_key"]) for w in data.get("wallets", [])]

    def _save(self) -> None:
        if not self.path:
            return
        directory = os.path.dirname(os.path.abspath(self.path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".wallets-", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"wallets": [asdict(w) for w in self.wallets]}, fh, indent=1)
        os.replace(tmp, self.path)

    def _unique_name(self, name: str) -> str:
        base = (name or "").strip() or "Wallet"
        names = {w.name for w in self.wallets}
        candidate, n = base, 2
        while candidate in names:
            candidate, n = f"{base} {n}", n + 1
        return candidate

    def create(self, name: str = "") -> Wallet:
        kp = generate_keypair()
        wallet = Wallet(self._unique_name(name or f"Wallet {len(self.wallets) + 1}"), kp["private_key"], kp["public_key"])
        self.wallets.append(wallet)
        self._save()
        return wallet

    def import_key(self, private_key: str, name: str = "") -> Wallet:
        """Add a wallet from its private key. Raises ``ValueError`` if the key is not one."""
        private_key = (private_key or "").strip()
        try:
            public_key = public_key_for(private_key)
        except Exception:  # noqa: BLE001 - any decode failure means "not a key"
            raise ValueError("that is not a PaSta private key") from None
        for w in self.wallets:
            if w.public_key == public_key:
                return w
        wallet = Wallet(self._unique_name(name or "Imported wallet"), private_key, public_key)
        self.wallets.append(wallet)
        self._save()
        return wallet

    def import_file(self, path: str, name: str = "") -> Wallet:
        """Import a backup file: ``{"private_key": ...}`` as written by any PaSta front-end."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "private_key" not in data:
            raise ValueError("no private_key in that file")
        return self.import_key(str(data["private_key"]), name or str(data.get("name") or ""))

    def export_file(self, wallet: Wallet, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"name": wallet.name, "private_key": wallet.private_key, "public_key": wallet.public_key}, fh, indent=1)

    def rename(self, wallet: Wallet, name: str) -> None:
        if name.strip() and name.strip() != wallet.name:
            wallet.name = self._unique_name(name)
            self._save()

    def remove(self, wallet: Wallet) -> None:
        self.wallets = [w for w in self.wallets if w.public_key != wallet.public_key]
        self._save()

    def by_address(self, address: str) -> Optional[Wallet]:
        return next((w for w in self.wallets if w.public_key == address), None)


# ------------------------------------------------------------------- flows ----

def _submit(backend: Any, wallet: Wallet, receiver: str, amount: int) -> Dict[str, Any]:
    """Sign and post. Timestamps have one-second resolution and are part of the transaction's
    identity, so an identical transaction in the same second gets the next free second."""
    known = {b.get("tx_id") for b in backend.get_blockchain()} | {t.get("tx_id") for t in backend.get_mempool()}
    ts = int(time.time())
    while compute_tx_id(wallet.address, receiver, amount, ts) in known:
        ts += 1
    for _ in range(5):
        signature = sign_transaction(wallet.private_key, wallet.address, receiver, amount, ts)
        try:
            return backend.create_transaction(wallet.address, receiver, amount, timestamp=ts, signature=signature)
        except InvalidTransaction as exc:
            if "duplicate" not in str(exc):
                raise
            ts += 1
    raise InvalidTransaction("could not find a free timestamp for this transaction")


def eligible_targets(backend: Any, address: str) -> List[Dict[str, Any]]:
    """Waiting (State B) transactions that ``address`` is allowed to finalize, oldest first."""
    return [t for t in backend.get_mempool() if t.get("state") == "B" and t.get("sender_address") != address]


def send_payment(backend: Any, wallet: Wallet, receiver: str, amount: int) -> Dict[str, Any]:
    """Post a payment and make it eligible. Returns ``{"tx", "validated", "note"}``.

    ``validated`` is the transaction this payment finalized on its way to State B, or None
    when nothing was waiting; the payment then stays in State A until something is.
    """
    receiver = (receiver or "").strip()
    if not receiver:
        raise InvalidTransaction("a receiver address is required")
    tx = _submit(backend, wallet, receiver, int(amount))
    targets = eligible_targets(backend, wallet.address)
    if not targets:
        return {"tx": tx, "validated": None,
                "note": "Sent. Nothing is waiting to be validated yet, so this payment waits at step 1."}
    try:
        result = backend.validate(tx["tx_id"], targets[0]["tx_id"])
    except PastaError as exc:
        return {"tx": tx, "validated": None, "note": f"Sent, but validating another transaction failed: {exc}"}
    return {"tx": result["my_tx"], "validated": result["finalized"],
            "note": "Sent. It is waiting for another user to confirm it."}


def confirm(backend: Any, wallet: Wallet, target_tx_id: str) -> Dict[str, Any]:
    """Finalize someone else's waiting transaction. Returns ``{"finalized", "my_tx"}``.

    Uses a State-A transaction of this wallet's if one is already waiting (so a payment
    stuck at step 1 moves on); otherwise posts a zero-amount transaction to do the job.
    """
    target = next((t for t in backend.get_mempool() if t.get("tx_id") == target_tx_id), None)
    if target is None:
        raise InvalidTransaction("that transaction is no longer waiting")
    if target.get("sender_address") == wallet.address:
        raise InvalidTransaction("you cannot confirm your own transaction; another wallet has to")
    mine = next((t for t in backend.get_mempool()
                 if t.get("state") == "A" and t.get("sender_address") == wallet.address), None)
    if mine is None:
        mine = _submit(backend, wallet, wallet.address, 0)
    result = backend.validate(mine["tx_id"], target_tx_id)
    return {"finalized": result["finalized"], "my_tx": result["my_tx"]}
