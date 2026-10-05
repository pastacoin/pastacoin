# PaSta technical specification (living document)

Status: **draft: Phase 1 rules plus the launch mint rule.** Everything here is implemented in
`pasta/` and covered by `tests/`. Later phases append sections; nothing here is final until the
whitepaper's open questions (chain shape, storage proof) are settled by simulation.

Where this document and the whitepaper disagree, the whitepaper states intent and this
document states what the code does today.

## 0. Units

Every amount (on the chain, in the signed payload, in the REST API, in a snapshot) is an
integer number of **base units**. One PASTA is 100,000,000 base units (`pasta/core/units.py`).
A non-integer amount is rejected. Front-ends convert at the edge; nothing in the protocol
handles a fractional number.

## 1. Identities and signatures

- An **address** is the Base58 encoding of a secp256k1 public key (64 raw bytes).
- The **canonical payload** of a transaction is compact JSON with sorted keys:
  `{"amount":<int base units>,"receiver":<addr>,"sender":<addr>,"timestamp":<int>}`.
- `tx_id = sha256(canonical_payload)` in hex. It never changes during the life-cycle.
- The **signature** is ECDSA over SHA-256 of the canonical payload, Base58 encoded.
- A node **rejects** any transaction whose signature does not verify against `sender`.
  Nobody can submit a transaction as `"GENESIS"`.
- Consequence: two transactions with identical sender, receiver, amount and timestamp
  (one-second resolution) have the same `tx_id`; the second is rejected as a duplicate.

## 2. Block

One transaction per block. Fields (see `pasta/core/models.py`):

| Group | Fields | Set when |
|---|---|---|
| Signed data | `sender_address`, `receiver_address`, `amount`, `timestamp`, `signature`, `tx_id` | creation |
| Stability | `mint_amount`, `average_tx_size` (the rule's smoothed median payment) | finalization |
| Linkage | `predecessor_id`, `predecessor_hash`, `level` | finalization |
| Balances | `sender_balance_before/after`, `receiver_balance_before/after` | finalization |
| Proof of validating another | `validated_block_id`, `validated_block_hash` | A -> B |
| Finalization | `validator_address`, `required_difficulty`, `nonce`, `block_hash`, `state` | B -> C |

Amount semantics: the sender pays `amount`; the receiver is credited `amount + mint_amount`.
A negative `mint_amount` is a burn taken from the receiver's credit; it never exceeds `amount`.
A transaction with `amount > 0` must have `sender != receiver`. A zero-amount transaction (to
anyone, including yourself) is allowed: it moves nothing and exists so that an address with
no coins can still validate.

## 3. State machine

```
A (created, signed, in mempool)
  --validate(target in B, target.sender != my.sender)-->  B (eligible; proof embedded)
  --someone else validates me-->  C (finalized, on chain)
```

`Node.validate(my_tx_id, target_tx_id)` performs both halves atomically:

1. `my_tx` must be in state A; `target` must be in state B; `target.sender != my_tx.sender`;
   `my_tx != target`.
2. `target.sender` must hold at least `target.amount` on chain (GENESIS exempt). If not, the
   target is dropped from the mempool and the call fails.
3. `target` is linked to the current chain tip, balances are filled in, `mint_amount` is set
   by the mint rule (section 7) from the chain as it stands, `validator_address = my_tx.sender`,
   `state = "C"`, `required_difficulty` is set from the node's difficulty for `target.level`,
   and proof-of-work is mined.
4. `target` is appended to the chain and removed from the mempool.
5. `my_tx.validated_block_id = target.tx_id`, `my_tx.validated_block_hash = target.block_hash`,
   `my_tx.state = "B"`.

There is no standalone "finalize" operation. The only way a transaction reaches C is by being
somebody else's validation target.

## 4. Proof of work

- `serialize(block)` = JSON with sorted keys of the block dict with `block_hash` and `nonce`
  set to `null`.
- `block_hash = sha256(serialize(block) + str(nonce))` must start with
  `"0" * required_difficulty`.
- Because serialization covers every other field, the validator, state, predecessor and
  balances are all committed to by the proof.

## 5. Genesis and bootstrap

- Block 0: `GENESIS -> <genesis receiver>`, amount 10 PASTA (1,000,000,000 base units),
  `predecessor_id = "GENESIS"`, `predecessor_hash = "0"`, `state = "C"`,
  `validator_address = "GENESIS"`, no signature, `block_hash = sha256(content)` (no PoW).
  **These are the only coins anyone is ever given.** The receiver is chosen by whoever starts
  the chain (`Node(genesis_receiver=...)`).
- A fresh node also places one **bootstrap transaction** (`GENESIS -> GENESIS`, 0, state B,
  pointing at block 0) in the mempool so the first real transaction has a target. It is the
  only block after block 0 that may name GENESIS as sender, and it carries nothing.

## 6. Balances

`balance(addr) = sum(amount + mint for blocks received) - sum(amount for blocks sent)`, chain only,
in base units, exact.
Admission of a new transaction requires `balance(sender) - pending_outgoing(sender) >= amount`,
where `pending_outgoing` is the sum of the sender's mempool amounts.

## 7. Mint rule (launch rule, issue #40)

All supply beyond the genesis credit is minted, or burned, by this rule
(`pasta/stability/chain.py`). It is a pure function of the chain.

- A **payment** is a finalized block with `amount > 0`, `sender != receiver`, sender not
  GENESIS. Other blocks carry `mint_amount = 0` and are not counted.
- Every **10 payments** close a **period**. At the boundary:
  1. `median` = median of the period's payments, ignoring any below 5 % of the previous
     period's median (dust floor).
  2. `stat` = exponential average of `median` (weight 0.05; the first period sets it).
  3. `signal = (stat - target) / target`, with `target` = **10 PASTA, declared**. It is not
     learned from the first transactions, which are gifts and tests rather than prices.
  4. `change = -0.02 * signal * supply`, limited to `±cap * supply`, where
     `cap = max(0.2 %, 2 % * min(1, 100,000 PASTA / supply))`: 2 % per period while the chain
     is small, tapering to 0.2 % once supply passes one million PASTA.
  5. `budget` = `change` truncated to base units; `flow` = total paid in the period.
- Each payment in the next period gets `mint_amount = budget * amount // flow` (the mirror
  image for a burn), never more than what is left of the budget, and a burn never more than
  the payment. Unspent budget lapses at the next boundary. The first period has no budget.
- The mint is credited to the **receiver**. The sender always pays exactly `amount`.
- `average_tx_size` on a block records `stat` (base units) as it stood when the block was
  finalized.

Why this shape: `docs/SIMULATION-RESULTS.md` (round two and the cold-start section). The
hybrid rule's step decomposition is not active at launch because its flow reference cannot be
learned from a ten-coin economy.

Known weaknesses, accepted for the prototype chain:

- While the rule is minting every period, **self-trading harvests the mint**. The only cost
  is proof-of-work per transaction. The whitepaper's defence is the storage-weighted user
  (not implemented).
- The controller's arithmetic is floating point, rounded to base units at each boundary.
  Python nodes agree exactly; an independent implementation must reproduce the same IEEE-754
  operations. A production rule needs fixed-point arithmetic.

## 8. Difficulty

Per level. Every `retarget_window` finalized blocks (default 2016) the node compares the mean
mining time with the level's target block time (600 s at level 0, halving per level, floor 1 s)
and moves difficulty up or down by one leading zero (never below 0).

## 9. Chain verification

`verify_chain(chain)` re-checks, from the chain alone: genesis shape and hash; for every other
block its `tx_id`, uniqueness, `predecessor_*` links, state C, presence of a validator that
differs from the sender, signature, proof-of-work at `required_difficulty`, that
`mint_amount` and `average_tx_size` equal what the mint rule yields for the chain up to that
block, and that the recorded balance fields match a running tally with no overdraft. Block 0
must credit exactly the genesis supply to a real address, and GENESIS may send nothing
afterwards. `GET /verify` exposes it.

## 10. REST API

| Method | Path | Body / result |
|---|---|---|
| GET | `/status` | height, `tip_hash`, mempool size, `units_per_pasta`, `genesis_receiver`, difficulty, and `stability` (supply, minted, burned, target, smoothed median, signal, period, budget, cap) |
| GET | `/blockchain` | list of blocks; `?from=N` returns the blocks from index N on |
| GET | `/mempool`, `/mempool/<tx_id>` | pending transactions |
| GET | `/balance/<address>` | `{balance, pending_outgoing}` in base units |
| GET | `/verify` | `{ok, problems}` |
| GET | `/generate_keypair` | new keypair (convenience; clients should generate locally) |
| POST | `/create_transaction` | `{sender, receiver, amount, timestamp, signature}` (amount in base units) -> 201 `{tx}` |
| POST | `/validate` | `{my_tx_id, target_tx_id}` -> `{my_tx, finalized}` |
| POST | `/advance_b`, `/advance_c` | 410 Gone |

Protocol rejections return HTTP 400 `{"error": <message>, "type": <exception class>}`.

## 11. Persistence

`Node(storage_path)` writes a JSON snapshot (`version` = 2, `blockchain`, `mempool`,
`difficulty`) atomically after every mutation and restores it on start; the mint rule's state
is rebuilt by replaying the chain. Version 1 snapshots (float amounts, placeholder mint) are
refused.

## 12. Following a seed

Until nodes exchange blocks with each other, one node orders the transactions of a chain: the
seed. `pasta.node.replica.Replica` is a node that follows one.

- It downloads the seed's chain (`GET /blockchain?from=N`) and applies the checks of section 9
  to every block, one at a time (`ChainVerifier`). A block that fails is refused and nothing
  after it is accepted.
- Balances and the mint rule's state come from the blocks it verified, not from the seed's
  answers.
- New transactions and validations are passed to the seed (`POST /create_transaction`,
  `POST /validate`).
- Each sync asks for the block at its own tip as well. If the seed no longer has that block,
  the replica stops following and reports that the seed's chain diverged (reset or rewritten);
  it keeps its verified copy until told to start over.
- It trusts the seed for the order of transactions and for the first genesis block it sees,
  and for nothing else.

## Open questions carried to later phases

- Hybrid step decomposition and a sybil-resistant user count for the mint rule (Phases 2 and 3).
- Bifurcation, layers, aggregation blocks, balance blocks (Phase 2 model, Phase 3 code).
- Size-scaled difficulty and validator counts; storage proof (Phase 3).
- Peer protocol and fork choice (Phase 3). Today a replica follows one seed.
- `POST /validate` carries no signature and the node does the proof-of-work, so anyone can
  advance anyone's transaction. The validator should sign, and mine, its own validation.
