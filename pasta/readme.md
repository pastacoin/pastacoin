# Pasta Python Package

This directory is an **installable Python package** that contains all
shared logic for the Pastacoin project.  Everything that is **not** user‐
interface specific lives here so that the CLI, REST node, and desktop GUI
can import the same code.

Structure
---------

```
pasta/
├─ core/          # Pure data-structures & crypto helpers
├─ validation/    # State-machine & proof-of-work logic
├─ node/          # Thread-safe Node abstraction + Flask blueprint helper
└─ frontends/     # UI layers (cli, web, desktop)
```

Public API
----------

```python
from pasta import Node, generate_keypair
```

* `Node` – in-memory blockchain node used by every front-end
* `generate_keypair()` – convenience wrapper that returns a secp256k1
  private/public pair encoded with Base-58

Running Tests
-------------

```
pip install -r requirements.txt
pytest
```

All tests are located in the top-level `tests/` directory and exercise the
package without requiring the GUIs or web server.
