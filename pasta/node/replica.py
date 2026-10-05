"""A node that follows another node.

Until nodes gossip with each other (Phase 3), one node orders transactions for a chain: the
seed. A :class:`Replica` turns any computer into a checking copy of it. It downloads the
seed's chain, verifies every block itself with :class:`pasta.validation.chain.ChainVerifier`
(signatures, proof-of-work, balances, every mint), keeps the verified copy on disk, and
sends new transactions to the seed. What it shows as a balance is what *it* computed from
blocks it checked, not what the seed claims.

It trusts the seed for two things only: the order of transactions, and the first genesis
block it is shown. If the seed later serves a chain that does not extend the verified copy
(a reset, or a rewrite), the replica stops following and says so.

The public methods mirror :class:`pasta.node.Node` so a front-end can drive either.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Any, Dict, List, Optional

import requests

from pasta.core import errors
from pasta.core.errors import PastaError
from pasta.core.units import UNITS_PER_PASTA
from pasta.stability.chain import LAUNCH_PARAMS, StabilityParams
from pasta.validation.chain import ChainVerifier, verify_chain

DEFAULT_SEED = "https://seed.pastacoin.org"


class SeedUnreachable(PastaError):
    """The seed did not answer (network down, wrong address, or the seed is offline)."""


class SeedClient:
    """The REST calls a replica makes. Protocol rejections come back as the same
    :class:`PastaError` subclasses a local node would raise."""

    def __init__(self, base_url: str, session: Any = None, timeout: float = 20.0) -> None:
        self.base = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    def _unwrap(self, response: Any) -> Any:
        try:
            body = response.json()
        except ValueError:
            raise SeedUnreachable(f"{self.base} did not answer like a PaSta node (HTTP {response.status_code})") from None
        if response.status_code >= 400:
            kind = getattr(errors, str(body.get("type", "")), PastaError) if isinstance(body, dict) else PastaError
            if not (isinstance(kind, type) and issubclass(kind, PastaError)):
                kind = PastaError
            raise kind(body.get("error", f"HTTP {response.status_code}") if isinstance(body, dict) else str(body))
        return body

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        try:
            return self._unwrap(self.session.get(f"{self.base}{path}", params=params, timeout=self.timeout))
        except requests.RequestException as exc:
            raise SeedUnreachable(self._why(exc)) from None

    def post(self, path: str, body: Dict[str, Any]) -> Any:
        try:
            return self._unwrap(self.session.post(f"{self.base}{path}", json=body, timeout=max(self.timeout, 120.0)))
        except requests.RequestException as exc:
            raise SeedUnreachable(self._why(exc)) from None

    def _why(self, exc: Exception) -> str:
        reason = "it did not answer in time" if isinstance(exc, requests.Timeout) else "no connection"
        return f"cannot reach {self.base} ({reason})"


class Replica:
    """A verified local copy of a seed's chain, plus pass-through for new transactions."""

    def __init__(
        self,
        seed_url: str = DEFAULT_SEED,
        storage_path: Optional[str] = None,
        *,
        stability_params: StabilityParams = LAUNCH_PARAMS,
        client: Optional[SeedClient] = None,
    ) -> None:
        self.seed_url = seed_url.rstrip("/")
        self.storage_path = storage_path
        self.stability_params = stability_params
        self.client = client or SeedClient(self.seed_url)
        self._lock = threading.RLock()

        self.blockchain: List[Dict[str, Any]] = []
        self.mempool: List[Dict[str, Any]] = []
        self._verifier = ChainVerifier(stability_params)
        self.online = False
        self.seed_height = 0
        self.last_error: Optional[str] = None      # why the last sync could not reach the seed
        self.diverged: Optional[str] = None        # set when the seed's chain stopped matching ours
        self.rejected: List[str] = []              # problems found in a block the seed served

        if storage_path and os.path.exists(storage_path):
            self._load()

    # ------------------------------------------------------------------ storage
    def _load(self) -> None:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as fh:  # type: ignore[arg-type]
                data = json.load(fh)
        except (OSError, ValueError):
            return
        if data.get("seed") != self.seed_url:
            return                                  # a copy of some other chain: ignore it
        for block in data.get("blockchain", []):
            if self._verifier.add(block):
                break                               # keep the prefix that verifies; resync the rest
            self.blockchain.append(block)

    def _save(self) -> None:
        if not self.storage_path:
            return
        directory = os.path.dirname(os.path.abspath(self.storage_path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".pasta-", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"seed": self.seed_url, "blockchain": self.blockchain}, fh)
            os.replace(tmp, self.storage_path)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # --------------------------------------------------------------------- sync
    def sync(self) -> int:
        """Fetch and verify whatever is new on the seed. Returns the number of blocks added.

        Never raises for an unreachable seed: ``online`` goes False and ``last_error`` says why.
        """
        with self._lock:
            try:
                status = self.client.get("/status")
                have = len(self.blockchain)
                blocks = self.client.get("/blockchain", params={"from": max(0, have - 1)})
                mempool = self.client.get("/mempool")
            except SeedUnreachable as exc:
                self.online = False
                self.last_error = str(exc)
                return 0
            self.online = True
            self.last_error = None
            self.seed_height = int(status.get("height", 0))
            self.mempool = list(mempool)

            # A node that ignores ?from= sends the whole chain: cut it ourselves.
            if have > 1 and blocks and blocks[0].get("predecessor_id") == "GENESIS":
                blocks = blocks[have - 1:]
            if have:
                tip = self.blockchain[-1].get("block_hash")
                if not blocks or blocks[0].get("block_hash") != tip:
                    self.diverged = (
                        f"The seed's chain no longer contains block {have - 1} of the copy on this computer. "
                        "The seed may have been reset, or its history rewritten."
                    )
                    return 0
                blocks = blocks[1:]
            self.diverged = None

            added = 0
            for block in blocks:
                problems = self._verifier.add(block)
                if problems:
                    self.rejected = problems
                    break
                self.blockchain.append(block)
                added += 1
            else:
                self.rejected = []
            if added:
                self._save()
            return added

    def reset(self) -> None:
        """Forget the local copy (after a divergence) and start again from the seed's genesis."""
        with self._lock:
            self.blockchain = []
            self.mempool = []
            self._verifier = ChainVerifier(self.stability_params)
            self.diverged = None
            self.rejected = []
            if self.storage_path and os.path.exists(self.storage_path):
                os.remove(self.storage_path)

    # ------------------------------------------------- the Node-shaped interface
    @property
    def genesis_receiver(self) -> str:
        return self.blockchain[0]["receiver_address"] if self.blockchain else ""

    def get_blockchain(self, start: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(b) for b in self.blockchain[max(0, int(start)):]]

    def get_mempool(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(t) for t in self.mempool]

    def balance_for(self, address: str) -> int:
        """Balance computed here, from blocks this computer verified."""
        with self._lock:
            return int(self._verifier.balances.get(address, 0))

    def pending_outgoing(self, address: str) -> int:
        with self._lock:
            return sum(int(tx.get("amount", 0)) for tx in self.mempool if tx.get("sender_address") == address)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "height": len(self.blockchain),
                "tip_hash": self.blockchain[-1].get("block_hash") if self.blockchain else None,
                "mempool_size": len(self.mempool),
                "units_per_pasta": UNITS_PER_PASTA,
                "genesis_receiver": self.genesis_receiver,
                "stability": self._verifier.stability.status(),
                "seed": {
                    "url": self.seed_url,
                    "online": self.online,
                    "height": self.seed_height,
                    "error": self.last_error,
                    "diverged": self.diverged,
                    "rejected": list(self.rejected),
                },
            }

    def verify(self) -> List[str]:
        """Re-check the whole local copy from scratch."""
        return verify_chain(self.get_blockchain(), self.stability_params)

    def create_transaction(self, sender: str, receiver: str, amount: int,
                           timestamp: Optional[int] = None, signature: Optional[str] = None) -> Dict[str, Any]:
        body = {"sender": sender, "receiver": receiver, "amount": amount,
                "timestamp": timestamp, "signature": signature}
        tx = self.client.post("/create_transaction", body)["tx"]
        with self._lock:
            self.mempool.append(tx)
        return tx

    def validate(self, my_tx_id: str, target_tx_id: str) -> Dict[str, Any]:
        result = self.client.post("/validate", {"my_tx_id": my_tx_id, "target_tx_id": target_tx_id})
        self.sync()
        return result
