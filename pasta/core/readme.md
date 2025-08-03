# `pasta.core`

Pure, UI-agnostic primitives that define **what a block is** and the
minimal cryptographic helpers required by the rest of the system.

Contents
--------
* `models.py` – `TransactionBlock` dataclass + `create_genesis()` helper
* `crypto.py`  – toy `generate_keypair()` built on *ecdsa* / *base58*

Nothing in this folder touches the network or disk; that makes it trivial
to unit-test and safe to reuse in any environment (desktop app, server,
scripts, etc.).
