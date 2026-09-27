from __future__ import annotations

"""Legacy entry-point: a Flask app around a single in-process Node.

Kept so ``from pasta.network.server import app`` and WSGI servers keep working.
Prefer ``python node.py`` or ``Node().create_flask_app()`` in new code.
"""

import os

from pasta.node import Node

_node = Node(os.getenv("PASTA_STORAGE") or None)
app = _node.create_flask_app(__name__)


def run(host: str = "0.0.0.0", port: int | None = None):
    """Start the built-in development server (threaded)."""
    app.run(host=host, port=int(port or os.getenv("PORT", 5000)), threaded=True)
