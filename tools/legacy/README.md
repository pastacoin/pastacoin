# Legacy tools (from the 2025 `master` branch)

These scripts predate the `pasta` package and write to `C:\PastaNetwork`. They are kept
because they hold the first cut of ideas that `main` has not re-implemented yet:

| File | What it did | Relevant to |
|---|---|---|
| `fake-blockchain-gen.py` | Random chain with real ecdsa signatures, `layer` field, `find_predecessor_and_layer()` (free chain ends vs. bifurcation), A/B/C hash fields, random mintburn | Phase 2 chain-shape simulator |
| `fake-mempool-gen.py` | Random pending transactions for the old file-based node | Phase 2 |
| `blockchain-visualizer.py` | Mermaid diagram of a chain grouped by layer | Phase 2 tooling |
| `blockchain_diagram.md` | Sample output of the visualizer | Reference |

They are not maintained and not covered by tests. Port ideas out of them; do not import them.
