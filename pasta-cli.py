"""Interactive REST client for a PaSta node.

The CLI never sends a private key anywhere: it signs the canonical payload locally and
posts ``sender, receiver, amount, timestamp, signature`` to the node.
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Any, Dict, List, Optional

import requests

from pasta.core.crypto import generate_keypair, public_key_for, sign_transaction


class NodeClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    # ---- helpers
    def _get(self, path: str) -> Any:
        r = requests.get(f"{self.base}{path}", timeout=10)
        return self._unwrap(r)

    def _post(self, path: str, body: Dict[str, Any]) -> Any:
        r = requests.post(f"{self.base}{path}", json=body, timeout=600)
        return self._unwrap(r)

    @staticmethod
    def _unwrap(r: requests.Response) -> Any:
        try:
            data = r.json()
        except ValueError:
            data = {"error": r.text}
        if r.status_code >= 400:
            raise RuntimeError(f"node said {r.status_code}: {data.get('error', data)}")
        return data

    # ---- API
    def status(self): return self._get("/status")
    def blockchain(self) -> List[Dict]: return self._get("/blockchain")
    def mempool(self) -> List[Dict]: return self._get("/mempool")
    def balance(self, address: str): return self._get(f"/balance/{address}")
    def verify(self): return self._get("/verify")

    def send(self, private_key: str, receiver: str, amount: float) -> Dict:
        sender = public_key_for(private_key)
        ts = int(time.time())
        sig = sign_transaction(private_key, sender, receiver, amount, ts)
        return self._post("/create_transaction", {
            "sender": sender, "receiver": receiver, "amount": amount, "timestamp": ts, "signature": sig,
        })

    def validate(self, my_tx_id: str, target_tx_id: str) -> Dict:
        return self._post("/validate", {"my_tx_id": my_tx_id, "target_tx_id": target_tx_id})


# ---------------------------------------------------------------- UI ----

def short(s: Optional[str], n: int = 10) -> str:
    return (s or "")[:n]


def print_mempool(mempool: List[Dict]) -> None:
    if not mempool:
        print("Mempool is empty.")
        return
    print(f"{'#':>2}  {'tx_id':<12} {'state':<5} {'sender':<12} {'receiver':<12} {'amount':>10} {'mint':>8}")
    for i, tx in enumerate(mempool):
        print(f"{i:>2}  {short(tx['tx_id'], 12):<12} {tx['state']:<5} {short(tx['sender_address'], 12):<12} "
              f"{short(tx['receiver_address'], 12):<12} {tx['amount']:>10.4f} {tx.get('mint_amount', 0):>8.3f}")


def print_chain(chain: List[Dict]) -> None:
    print(f"{'h':>3}  {'hash':<12} {'sender':<12} {'receiver':<12} {'amount':>10} {'mint':>8} {'validator':<12}")
    for h, b in enumerate(chain):
        print(f"{h:>3}  {short(b.get('block_hash'), 12):<12} {short(b['sender_address'], 12):<12} "
              f"{short(b['receiver_address'], 12):<12} {b['amount']:>10.4f} {b.get('mint_amount', 0):>8.3f} "
              f"{short(b.get('validator_address'), 12):<12}")


def pick(mempool: List[Dict], prompt: str, allowed_states: set) -> Optional[Dict]:
    options = [tx for tx in mempool if tx["state"] in allowed_states]
    if not options:
        print(f"No mempool transactions in state {sorted(allowed_states)}.")
        return None
    print_mempool(options)
    raw = input(f"{prompt} (row number, blank to cancel): ").strip()
    if not raw:
        return None
    try:
        return options[int(raw)]
    except (ValueError, IndexError):
        print("Invalid row.")
        return None


def main_menu(client: NodeClient) -> None:
    while True:
        print(f"\n--- PaSta CLI @ {client.base} ---")
        print("1. Generate new keypair")
        print("2. Send PASTA (creates a State A transaction)")
        print("3. View mempool")
        print("4. View blockchain")
        print("5. Check balance")
        print("6. Validate: move my transaction to State B by finalizing another (State C)")
        print("7. Verify chain")
        print("8. Node status")
        print("9. Exit")
        choice = input("Choice: ").strip()
        try:
            if choice == "1":
                kp = generate_keypair()
                print(f"\nPrivate key: {kp['private_key']}\nAddress:     {kp['public_key']}")
                print("SAVE THESE. The node never sees the private key.")
            elif choice == "2":
                priv = input("Your private key: ").strip()
                receiver = input("Receiver address: ").strip()
                amount = float(input("Amount (0 = zero-value, may mint during bootstrap): ").strip() or "0")
                res = client.send(priv, receiver, amount)
                tx = res["tx"]
                print(f"\n{res['message']}: tx_id {tx['tx_id']}  mint {tx['mint_amount']}")
                print("Next: option 6 to validate another transaction and move yours to State B.")
            elif choice == "3":
                print_mempool(client.mempool())
            elif choice == "4":
                print_chain(client.blockchain())
            elif choice == "5":
                addr = input("Address: ").strip()
                b = client.balance(addr)
                print(f"Balance {b['balance']} PASTA (pending outgoing {b['pending_outgoing']})")
            elif choice == "6":
                mem = client.mempool()
                mine = pick(mem, "Your State A transaction", {"A"})
                if not mine:
                    continue
                target = pick([t for t in mem if t["sender_address"] != mine["sender_address"]],
                              "Eligible target (State B, different sender)", {"B"})
                if not target:
                    continue
                print("Mining...")
                res = client.validate(mine["tx_id"], target["tx_id"])
                fin = res["finalized"]
                print(f"\n{res['message']}.")
                print(f"Finalized block hash {fin['block_hash']} (difficulty {fin['required_difficulty']})")
            elif choice == "7":
                v = client.verify()
                print("Chain OK" if v["ok"] else "PROBLEMS:\n  " + "\n  ".join(v["problems"]))
            elif choice == "8":
                print(json.dumps(client.status(), indent=2))
            elif choice == "9":
                print("Goodbye!")
                return
            else:
                print("Invalid choice.")
        except (RuntimeError, ValueError, requests.RequestException) as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PaSta CLI client")
    parser.add_argument("--node", default="http://localhost:5000", help="Node base URL")
    args = parser.parse_args()
    client = NodeClient(args.node)
    try:
        s = client.status()
        print(f"Connected to {args.node}: height {s['height']}, mempool {s['mempool_size']}")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: could not reach node at {args.node}: {exc}")
    main_menu(client)
