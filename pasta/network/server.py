from __future__ import annotations

"""Legacy entry-point that exposes a Flask REST server backed by the new
`pasta.node.Node` abstraction.  Existing scripts that import
`pasta.network.server:app` or `run()` will keep working.
"""

import os
import argparse

from pasta.node import Node

# Single in-process node
_node = Node()
app = _node.create_flask_app(__name__)


def run(host: str = "0.0.0.0", port: int | None = None):
    """Start the built-in development server (threaded)."""
    if port is None:
        port = int(os.getenv("PORT", 5000))
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PastaCoin REST server")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    run(port=args.port)
