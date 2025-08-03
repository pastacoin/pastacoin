# `pasta.validation`

Implements the **State A → B → C** life-cycle for Pastacoin blocks plus
a tiny proof-of-work mining helper.

Files
-----
* `engine.py`
  * `build_state_a()` – create a new transaction
  * `advance_to_state_b()` – attach PoW proof validating another block
  * `advance_to_state_c()` – finalise block with its own PoW

The difficulty is intentionally low because this code is meant for
educational demos, not main-net security.
