# PaSta Coin: Passively Stable Cryptocurrency

PaSta is a novel blockchain architecture designed to create a practical, scalable cryptocurrency for everyday transactions. PaSta is a Proof-of-Work type cryptocurrency, relies on "longest chain" consensus rules and in many other additional ways relies heavily on learnings from the Bitcoin Blockchain. It addresses three fundamental challenges in current cryptocurrency systems: price stability, transaction throughput, and decentralized validation.

A working draft of the whitepaper describing this project can be found here: https://docs.google.com/document/d/16TWRU0hxGe5E3mB4EnAzSYjfOsMuH8AT/edit?usp=sharing&ouid=113569012516612057458&rtpof=true&sd=true

## Key Features

### Algorithmic Stability Control
Unlike traditional stablecoins that require pegging to external currencies, PaSta implements internal stability mechanisms that:
- Monitor average transaction sizes across the network to detect price trends
- Automatically adjust money supply through small minting or burning operations within transactions

### Dynamic Chain Architecture
PaSta enables parallel processing through a scalable chain structure:
- One transaction per block
- Controlled chain bifurcation allows splits when the network is saturated
- Aggregation blocks merge blocks back towards the main chain
- Block times get shorter the further from the main chain a block gets (layering)
- If a block initiates a split, it must also perform an aggregation to be eligible for validation
- Balance blocks serve as validated checkpoints to optimize transaction history
- Maintains eventual consistency while enabling dramatically higher throughput

### User-Based Validation
Instead of relying on dedicated miners, PaSta distributes validation among network participants:
- Instead of miners competing for a coin reward, users compete to have their transactions accepted
- Prior to a transaction block being eligible for validation the node must first validate other transactions
- Once a block is eligible for validation other users must validate it
- Transaction privileges are tied directly to blockchain storage contribution
- Higher layer transactions (further from the main chain, smaller block time) process quickly with minimal validation
- Number of validators scales perfectly with number of transactions (because the nodes executing transactions are also the validators)

## Core Components

### PastaMachine (Full Node)
- Chain data management
- Transaction processing
- Validation mechanisms
- Stability control
- State management
- Network communication

### PastaWallet (Light Client)
- Basic transaction creation
- Local validation
- Balance management
- User interface
- Address book

### PastaMonitor
- Network visualization
- Chain state monitoring
- Performance metrics
- Development tools

### PastaTester
- Network simulation
- Stability testing
- Attack modeling
- Performance testing

## Design Philosophy

PaSta is designed specifically as a medium of exchange rather than a store of value or investment vehicle. Its value is programmed to remain the same over time:
- Discourages speculative investment and hoarding
- Promotes active use in transactions
- Minimizes short-term value fluctuations
- May help distinguish it from commodities or investment assets (from a regulatory perspective)

## Development Status

**Prototype with a public test chain.** A Python package (`pasta/`) implements the node (State
A -> B -> C validation life-cycle, toy proof-of-work, the launch mint rule), a REST API, an
interactive CLI, and a desktop wallet-and-node ("The Pasta Machine"). A public node runs at
`https://seed.pastacoin.org`; the browser wallet at [pastacoin.org/prototype](https://pastacoin.org/prototype/)
and the desktop app both use it. The desktop app keeps its own copy of the chain and checks
every block itself.

**Try it:** download `PastaMachine.exe` from the
[latest release](https://github.com/pastacoin/pastacoin/releases/latest) (Windows, built by
GitHub Actions from source), or open the browser wallet. The coins are test coins with no value.

Still missing from the whitepaper: chain bifurcation, balance blocks, storage proof, and
node-to-node networking (one node, the seed, orders transactions for now). The full gap table and the phased plan live in
[`docs/STATUS-2026-09-26.md`](docs/STATUS-2026-09-26.md). Every document the work is done
against is indexed in [`docs/README.md`](docs/README.md). The backlog is the GitHub issue list.

## Quick Start

Requires Python 3.11 or 3.12.

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev,gui]"     # drop ",gui" if you do not need the desktop app
.venv/Scripts/python -m pytest -q
```

Run the REST node and the CLI in two terminals:

```bash
.venv/Scripts/python node.py                                   # http://localhost:5000
.venv/Scripts/python pasta-cli.py --node http://localhost:5000
```

Run the desktop app (follows the public seed by default; `Network` menu for a private chain
or another node; `PASTA_SEED` and `PASTA_HOME` override the node and the data folder):

```bash
.venv/Scripts/python -m pasta.frontends.desktop
```

Build the Windows executable (`dist/PastaMachine.exe`, not committed). Releases are built the
same way by `.github/workflows/release.yml` when a `v*` tag is pushed:

```bash
.venv/Scripts/pip install pyinstaller
.venv/Scripts/pyinstaller PastaMachine.spec
```

Run your own public node: see [`deploy/README.md`](deploy/README.md).

### Transaction life-cycle in the prototype

0. Start a node (`python node.py --storage chain.json`). A new chain writes
   `genesis-wallet.json` next to the chain file: that key holds the 10 PASTA the genesis block
   creates, the only coins anyone is ever given. Everything else is minted by the stability
   rule as payments happen (`docs/SPEC.md` section 7).
1. Generate two keypairs (CLI option 1). The public key is the address; the private key never
   leaves the client.
2. Send a transaction (option 2). The CLI signs the canonical payload locally; the node verifies
   the signature and the sender's balance, then admits it to the mempool in **State A**.
3. Validate (option 6): pick your State A transaction and a State B target from a *different*
   sender. Yours moves to **State B**; the target is finalized to **State C** with you recorded
   as validator, proof-of-work is mined, and it is appended to the blockchain.
4. Check the blockchain, balances and chain integrity (options 4, 5 and 7).

The rules the node enforces are written down in [`docs/SPEC.md`](docs/SPEC.md).

The genesis block starts in State C and a bootstrap transaction sits in the mempool in State B
so that the first real transaction has something to validate. An address with no coins can
still validate by sending a zero-amount transaction. Amounts on the wire are whole base units
(1 PASTA = 100,000,000); the CLI and the desktop app accept and show PASTA.

## Repository Layout

```
pasta/            installable package (core, validation, node, network, frontends)
tests/            pytest suite
tools/legacy/     2025 scripts kept for reference (fake chain generator, visualizer)
docs/             status, plan, documentation register
pasta-cli.py      REST client
node.py           REST server entry point
PastaMachine.spec PyInstaller spec for the desktop app
```

## Contributing

While we're still in early stages, we welcome discussion and contributions from developers interested in:
- Blockchain architecture
- Cryptocurrency stability mechanisms
- Distributed systems
- Network security
- Economic modeling
- User interface design

---
*Note: This project is under active development. Features and specifications are subject to change as we refine the system architecture and implementation details.*
