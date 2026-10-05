"""Run a PaSta REST node: ``python node.py [--port N] [--storage path] [--genesis-address ADDR]``.

With ``--storage`` the chain is kept in that file and reopened on the next start. A new chain
needs an address for the genesis coins: pass ``--genesis-address`` (or set
``PASTA_GENESIS_ADDRESS``), or let the launcher generate a wallet and write it next to the
chain file as ``genesis-wallet.json``.
"""
import argparse
import json
import os

from pasta.core.units import format_units
from pasta.node import open_node

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a PaSta REST node")
    parser.add_argument("--port", "-p", type=int, default=int(os.getenv("PORT", 5000)))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--storage", default=os.getenv("PASTA_STORAGE"), help="JSON snapshot path (optional)")
    parser.add_argument("--genesis-address", default=os.getenv("PASTA_GENESIS_ADDRESS"),
                        help="address credited with the genesis coins when starting a new chain")
    args = parser.parse_args()

    node, new_key = open_node(args.storage, args.genesis_address)
    if new_key:
        wallet_path = os.path.join(os.path.dirname(os.path.abspath(args.storage)) if args.storage else ".",
                                   "genesis-wallet.json")
        with open(wallet_path, "w", encoding="utf-8") as fh:
            json.dump(new_key, fh, indent=1)
        print(f"New chain. The genesis coins belong to the key saved in {wallet_path}; keep it safe.")
    s = node.status()
    print(f"Chain height {s['height']}, supply {format_units(s['stability']['supply'])} PASTA, "
          f"genesis address {s['genesis_receiver'][:16]}...")
    node.start_rest_server(host=args.host, port=args.port)
