# Documentation register

The running list of every document the PaSta work is being done against. Update this table
whenever a document is added, moved, superseded, or materially revised. Newest entries at the
bottom of each section.

## Design authority

| Document | Location | Purpose | Status |
|---|---|---|---|
| PaSta Description (whitepaper) | Google Drive, folder "19 PaSta Coin (2024)", file id `16TWRU0hxGe5E3mB4EnAzSYjfOsMuH8AT` | Defines the three mechanisms: passive stability, dynamic chain, user-based validation. Contains diagrams (validation token, storage proof, bifurcation) that exist only as images in the .docx. | Working draft, last edited 2025-08-12. Authoritative until a technical spec exists. |
| Covacoco (2017) and Nano-C (2018) | Drive, subfolder "Covacoco + Nano-C lineage (superseded by PaSta)" | Ancestor designs. Nano-C's mint/burn-during-transaction idea survives in PaSta. | Superseded. Reference only. |
| Technical specification | `docs/SPEC.md` | Precise rules a node follows today: canonical payload, tx_id, block fields, state machine, PoW, genesis, balances, mint placeholder, difficulty, verification, REST API, persistence. | Live draft since 2026-09-27 (Phase 1 rules). Grows each phase; completed in Phase 4. |

## Project management

| Document | Location | Purpose | Status |
|---|---|---|---|
| Status and improvement plan | `docs/STATUS-2026-09-26.md` | Where the project stands, whitepaper-vs-code gap table, phased plan, changelog. | Live. Append to changelog every session. |
| This register | `docs/README.md` | Index of all documents worked against. | Live. |
| Backlog | GitHub issues on `pastacoin/pastacoin`, labels `phase-0` to `phase-5` | One issue per work item. Closed by PRs. | Live from 2026-09-26. |
| Big Idea Box ranking | Drive sheet "Big Idea Box — Master Idea Ranking (Aug 2026)" | External context: PaSta ranked #3 of 20 shelved ideas; cold-start risk noted. | Reference. |

## Developer-facing

| Document | Location | Purpose | Status |
|---|---|---|---|
| README | `README.md` | Public description, quick start, current status. | Live. |
| Claude working notes | `CLAUDE.md` | How to run, test, build, and talk to GitHub. Conventions. | Live. |
| Package readmes | `pasta/readme.md`, `pasta/core/readme.md`, `pasta/validation/readme.md`, `pasta/network/readme.md` | Per-package intent. | Refreshed 2026-09-27. |
| Legacy tools | `tools/legacy/README.md` | What the 2025 master-branch scripts did and which phase they inform. | Live. |
| Simulation results memo | `docs/SIMULATION-RESULTS.md` (planned) | Findings from PastaTester on the stability controller and chain shape. Feeds back into whitepaper. | Not started. Phase 2 deliverable. |

## Public surface

| Document | Location | Purpose | Status |
|---|---|---|---|
| Website | repo `pastacoin/pastacoin.github.io`, serves `pastacoin.org` | Landing page plus `/prototype/` web client. | Landing live. Prototype broken: its backend `pastacoin.onrender.com` is down and it posts private keys to the server. Phase 4. |

## Automation (planned)

| Document | Location | Purpose | Status |
|---|---|---|---|
| Perpetual improvement agent | `docs/AGENT.md` (planned) | Design for a remotely reachable agent with a daily scheduled run that reads this register and the status doc, picks the next backlog item, ships a PR, and updates the changelog. | Not started. Phase 5. |
