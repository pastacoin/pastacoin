# `pasta.core`

Pure primitives. Nothing here touches the network, disk or node state.

* `models.py` - `TransactionBlock` dataclass (one transaction = one block), `create_genesis()`,
  `from_dict()` tolerant of unknown keys, `compute_hash()` content hash.
* `crypto.py` - secp256k1 keypairs, the **canonical payload**, `compute_tx_id`,
  `sign_transaction` / `verify_transaction` (SHA-256). Every client and the node import the
  payload format from here so they cannot drift apart.
* `errors.py` - `PastaError` hierarchy the node raises and front-ends display.
