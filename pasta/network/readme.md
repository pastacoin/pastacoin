# `pasta.network`

Legacy label kept for backward-compatibility; new code lives in
`pasta.node`.  The module `pasta.network.server` is now just a **thin
wrapper** that spins up a Flask app backed by a `Node` instance so that
old scripts like `python node.py` continue to work.

For new development import directly:

```python
from pasta import Node
app = Node().create_flask_app()
app.run()
```
