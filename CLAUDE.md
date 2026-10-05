# PaSta Coin — working notes for Claude

PaSta ("Passively Stable") is an experimental proof-of-work cryptocurrency prototype.
Design authority is the whitepaper `PaSta Description.docx` in Google Drive
(folder "19 PaSta Coin (2024)", file id 16TWRU0hxGe5E3mB4EnAzSYjfOsMuH8AT).
Current project status and roadmap: `docs/STATUS-2026-09-26.md`. Register of every document worked against: `docs/README.md` (keep it current). Backlog: GitHub issues labelled `phase-N`.

## Environment

- Python 3.11 venv at `.venv` (PySide6 6.11 installed). Python 3.14 is the system default; do not use it.
- Package is installed editable (`pip install -e ".[dev,gui]"`, config in `pyproject.toml`): `from pasta import Node` works from anywhere in the venv.
- Run tests: `.venv/Scripts/python -m pytest -q`
- Run REST node: `.venv/Scripts/python node.py --storage chain.json` (port 5000; a new chain writes `genesis-wallet.json`) then `.venv/Scripts/python pasta-cli.py --node http://localhost:5000`
- Run simulator: `.venv/Scripts/python -m pasta.sim --compare --shock 2000:money_demand:1.5`
- Bitcoin analysis: `.venv/Scripts/python -m pasta.analysis.bitcoin_report --figures docs/figures --js ../pastacoin.github.io/results/bitcoin-data.js` (add `--fetch` to refresh `data/bitcoin-daily.csv`).
- Multi-chain analysis: `.venv/Scripts/python -m pasta.analysis.chains_report --figures docs/figures --js ../pastacoin.github.io/results/chains-data.js` (`--fetch ltc doge ...` to refresh; Blockchair blocks bulk pulls, so refresh one chain at a time).
- Regenerate figures + site data: `.venv/Scripts/python -m pasta.sim.report --figures docs/figures --js ../pastacoin.github.io/results/data.js` (needs `pip install matplotlib`), then commit both repos.
- Run desktop GUI: `.venv/Scripts/python -m pasta.frontends.desktop` (follows https://seed.pastacoin.org; set `PASTA_HOME` to a scratch folder and `PASTA_SEED` to a local node when testing). To look at it without opening a window: `QT_QPA_PLATFORM=offscreen` plus `QT_QPA_FONTDIR=C:\Windows\Fonts`, then `window.grab().save(png)`.
- Release: bump `version` in `pyproject.toml`, merge, `git tag vX.Y.Z && git push origin vX.Y.Z`; the `release` workflow tests, builds `PastaMachine.exe` and publishes it. The site links to `releases/latest/download/PastaMachine.exe`.
- Seed server: `deploy/README.md`. Update it with `bash /root/pastacoin/deploy/setup.sh seed.pastacoin.org main` after `git -C /root/pastacoin pull`.
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
    pasta/node        Node: in-memory blockchain + mempool, difficulty retarget, Flask app; open_node()
                      replica.py: Replica follows a seed over REST and verifies every block itself
    pasta/wallet.py   WalletStore (named keypairs in a JSON file) and the send / confirm flows
    pasta/network     Legacy thin wrapper around Node.create_flask_app
    pasta/stability   mint/burn controllers (pure policy objects) shared by the sim and the chain;
                      chain.py is the launch mint rule the Node and verify_chain both replay
    pasta/sim         PastaTester agent-based economy; python -m pasta.sim --help
    pasta/analysis    real-chain analyses (Bitcoin fixed-supply demonstration)
    data/             committed datasets (bitcoin-daily.csv)
    pasta/frontends   PySide6 desktop wallet-and-node ("The Pasta Machine"), one file: desktop/app.py
    deploy/           seed node setup (setup.sh, systemd unit, Caddyfile), release notes
    pasta-cli.py      Interactive REST client
    tests/            pytest
    tools/legacy      2025 master-branch scripts, reference only
    docs/             STATUS, documentation register

## Conventions

- Keep `pasta/` UI-agnostic; front-ends drive a `Node` or a `Replica` (same method names) and use `pasta/wallet.py` for send and confirm.
- In a bash heredoc on this machine `\\` collapses to one backslash; write files that contain backslashes with a file-writing tool instead.
- `pasta/validation/engine.py` performs transitions; `Node` decides whether they are allowed. Keep it that way.
- The canonical signed payload lives only in `pasta/core/crypto.py`; every client imports it.
- Mempool entries are addressed by `tx_id`, never by list index.
- Rules that the code enforces are written down in `docs/SPEC.md`; change both together.
- Do not commit `build/`, `dist/`, `__pycache__`, `*.egg-info` (see `.gitignore`).
- Amounts are integer base units everywhere inside `pasta/` (`pasta/core/units.py`); only front-ends convert to and from PASTA.
- Coins enter two ways only: the genesis credit (10 PASTA to `genesis_receiver`) and the mint rule in `pasta/stability/chain.py`. Its constants are consensus rules: changing one changes every `mint_amount`, so change `docs/SPEC.md` section 7 and the tests with it.
- A new chain needs `Node(genesis_receiver=...)`; `open_node()` generates a wallet when none is given. Tests use the `founder` fixture and the `pay()` helper in `tests/conftest.py`.
