"""Run a PaSta REST node: ``python node.py [--port N] [--storage path]``."""
import argparse
import os

from pasta import Node

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a PaSta REST node")
    parser.add_argument("--port", "-p", type=int, default=int(os.getenv("PORT", 5000)))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--storage", default=os.getenv("PASTA_STORAGE"), help="JSON snapshot path (optional)")
    args = parser.parse_args()
    Node(args.storage).start_rest_server(host=args.host, port=args.port)
