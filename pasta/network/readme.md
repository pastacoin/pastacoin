# `pasta.network`

Legacy label. `pasta.network.server` builds a Flask app around a single `Node` so
`python node.py` keeps working. New code should use `Node().create_flask_app()` directly.
Peer-to-peer networking (Phase 3) will live here.
