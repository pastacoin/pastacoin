# PaSta Coin — working notes for Claude

PaSta ("Passively Stable") is an experimental proof-of-work cryptocurrency prototype.
Design authority is the whitepaper `PaSta Description.docx` in Google Drive
(folder "19 PaSta Coin (2024)", file id 16TWRU0hxGe5E3mB4EnAzSYjfOsMuH8AT).
Current project status and roadmap: `docs/STATUS-2026-09-26.md`. Register of every document worked against: `docs/README.md` (keep it current). Backlog: GitHub issues labelled `phase-N`.

## Environment

- Python 3.11 venv at `.venv` (PySide6 6.11 installed). Python 3.14 is the system default; do not use it.
- Package is installed editable (`pip install -e ".[dev,gui]"`, config in `pyproject.toml`): `from pasta import Node` works from anywhere in the venv.
- Run tests: `.venv/Scripts/python -m pytest -q`
- Run REST node: `.venv/Scripts/python node.py` (port 5000) then `.venv/Scripts/python pasta-cli.py --node http://localhost:5000`
- Run simulator: `.venv/Scripts/python -m pasta.sim --compare --shock 2000:money_demand:1.5`
- Bitcoin analysis: `.venv/Scripts/python -m pasta.analysis.bitcoin_report --figures docs/figures --js ../pastacoin.github.io/results/bitcoin-data.js` (add `--fetch` to refresh `data/bitcoin-daily.csv`).
- Multi-chain analysis: `.venv/Scripts/python -m pasta.analysis.chains_report --figures docs/figures --js ../pastacoin.github.io/results/chains-data.js` (`--fetch ltc doge ...` to refresh; Blockchair blocks bulk pulls, so refresh one chain at a time).
- Regenerate figures + site data: `.venv/Scripts/python -m pasta.sim.report --figures docs/figures --js ../pastacoin.github.io/results/data.js` (needs `pip install matplotlib`), then commit both repos.
- Run desktop GUI: `.venv/Scripts/python -m pasta.frontends.desktop`
- Build Windows exe: `pyinstaller PastaMachine.spec` (output in `dist/`, ignored by git)

## GitHub

Org `pastacoin`, repos `pastacoin` (this) and `pastacoin.github.io` (site, cloned at `..\pastacoin.github.io`, serves pastacoin.org).
`git push/pull` route the pastacoin token automatically. For `gh` commands prefix with the org token:

    GH_TOKEN=$PASTACOIN_GH_TOKEN gh <command> -R pastacoin/pastacoin

Default branch is `main`. `master` is a stale 2025 branch; its unique files were copied to `tools/legacy/`.
Work on a branch, open a PR, let the `tests` workflow pass, then merge.

## Layout

    pasta/core        TransactionBlock dataclass, genesis, ecdsa/base58 key + sign helpers
    pasta/validation  State A -> B -> C engine with toy PoW (mine_pow, prefix param)
    pasta/node        Node: in-memory blockchain + mempool, minting, difficulty retarget, Flask app
    pasta/network     Legacy thin wrapper around Node.create_flask_app
    pasta/stability   mint/burn controllers (pure policy objects), shared by sim and (later) Node
    pasta/sim         PastaTester agent-based economy; python -m pasta.sim --help
    pasta/analysis    real-chain analyses (Bitcoin fixed-supply demonstration)
    data/             committed datasets (bitcoin-daily.csv)
    pasta/frontends   PySide6 desktop GUI ("The Pasta Machine")
    pasta-cli.py      Interactive REST client
    tests/            pytest
    tools/legacy      2025 master-branch scripts, reference only
    docs/             STATUS, documentation register

## Conventions

- Keep `pasta/` UI-agnostic; frontends import `Node` only.
- `pasta/validation/engine.py` performs transitions; `Node` decides whether they are allowed. Keep it that way.
- The canonical signed payload lives only in `pasta/core/crypto.py`; every client imports it.
- Mempool entries are addressed by `tx_id`, never by list index.
- Rules that the code enforces are written down in `docs/SPEC.md`; change both together.
- Do not commit `build/`, `dist/`, `__pycache__`, `*.egg-info` (see `.gitignore`).
- The bootstrap mint (zero-value tx mints toward a 10 PASTA average) is a placeholder for the Phase 2 controller; do not "fix" it in isolation.
