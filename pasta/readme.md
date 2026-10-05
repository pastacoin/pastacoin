# `pasta` package

Installable package holding all UI-agnostic logic. The CLI, REST node and desktop GUI all
drive the same `Node`.

```
pasta/
├─ core/          TransactionBlock, canonical payload + signatures, protocol exceptions
├─ validation/    A -> B -> C transitions, proof-of-work, verify_chain
├─ node/          Node: rules, mempool, chain, persistence, Flask app
├─ network/       legacy wrapper (python node.py)
└─ frontends/     desktop wallet-and-node (PySide6)
```

Public API: `from pasta import Node, generate_keypair, sign_transaction, verify_chain, PastaError`.
Rules are specified in `docs/SPEC.md`. Tests: `python -m pytest -q` from the repo root.
