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

**Prototype, single node.** A Python package (`pasta/`) implements a `TransactionBlock` model,
an in-memory node with the State A -> B -> C validation life-cycle and toy proof-of-work, a
REST API, an interactive CLI, and a PySide6 desktop app ("The Pasta Machine").

Most whitepaper mechanisms are not implemented yet (stability controller, chain bifurcation,
balance blocks, storage proof, networking). The full gap table and the phased plan live in
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

Run the desktop app:

```bash
.venv/Scripts/python -m pasta.frontends.desktop
```

Build the Windows executable (output in `dist/`, not committed):

```bash
.venv/Scripts/pip install pyinstaller
.venv/Scripts/pyinstaller PastaMachine.spec
```

### Transaction life-cycle in the prototype

1. Generate two keypairs (CLI option 1). The public key is the address.
2. Create a transaction (option 2). It enters the mempool in **State A**.
3. Validate another mempool transaction with yours (option 7). Yours moves to **State B**; the
   transaction you validated is finalized to **State C** and appended to the blockchain.
4. Check the blockchain and balances (options 4 and 5).

The genesis block starts in State C and a bootstrap transaction sits in the mempool in State B
so that the first real transaction has something to validate.

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
