# PaSta technical specification (living document)

Status: **draft, Phase 1 rules only.** Everything here is implemented in `pasta/` and covered
by `tests/`. Later phases append sections; nothing here is final until the whitepaper's
open questions (stability controller, chain shape, storage proof) are settled by simulation.

Where this document and the whitepaper disagree, the whitepaper states intent and this
document states what the code does today.

## 1. Identities and signatures

- An **address** is the Base58 encoding of a secp256k1 public key (64 raw bytes).
- The **canonical payload** of a transaction is compact JSON with sorted keys:
  `{"amount":<float>,"receiver":<addr>,"sender":<addr>,"timestamp":<int>}`.
- `tx_id = sha256(canonical_payload)` in hex. It never changes during the life-cycle.
- The **signature** is ECDSA over SHA-256 of the canonical payload, Base58 encoded.
- A node **rejects** any transaction whose signature does not verify against `sender`,
  except when `sender == "GENESIS"`.
- Consequence: two transactions with identical sender, receiver, amount and timestamp
  (one-second resolution) have the same `tx_id`; the second is rejected as a duplicate.

## 2. Block

One transaction per block. Fields (see `pasta/core/models.py`):

| Group | Fields | Set when |
|---|---|---|
| Signed data | `sender_address`, `receiver_address`, `amount`, `timestamp`, `signature`, `tx_id` | creation |
| Stability | `mint_amount`, `average_tx_size` | creation |
| Linkage | `predecessor_id`, `predecessor_hash`, `level` | finalization |
| Balances | `sender_balance_before/after`, `receiver_balance_before/after` | finalization |
| Proof of validating another | `validated_block_id`, `validated_block_hash` | A -> B |
| Finalization | `validator_address`, `required_difficulty`, `nonce`, `block_hash`, `state` | B -> C |

Amount semantics: the sender pays `amount`; the receiver is credited `amount + mint_amount`.
A negative `mint_amount` is a burn taken from the receiver's credit.

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
3. `target` is linked to the current chain tip, balances are filled in,
   `validator_address = my_tx.sender`, `state = "C"`, `required_difficulty` is set from the
   node's difficulty for `target.level`, and proof-of-work is mined.
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

- Block 0: `GENESIS -> GENESIS`, amount 0, `predecessor_id = "GENESIS"`,
  `predecessor_hash = "0"`, `state = "C"`, `validator_address = "GENESIS"`, no signature,
  `block_hash = sha256(content)` (no PoW).
- A fresh node also places one **bootstrap transaction** (`GENESIS -> GENESIS`, 0, state B,
  pointing at block 0) in the mempool so the first real transaction has a target.

## 6. Balances

`balance(addr) = sum(amount + mint for blocks received) - sum(amount for blocks sent)`, chain only.
Admission of a new transaction requires `balance(sender) - pending_outgoing(sender) >= amount`,
where `pending_outgoing` is the sum of the sender's mempool amounts.

## 7. Experimental mint (placeholder)

For the first 100,000 transactions, a zero-amount transaction mints
`max(0, 10 - average_value)` where `average_value` is the mean of `amount + mint` over all
admitted transactions. This exists only so the prototype has coins to move; Phase 2 replaces
it with the whitepaper's controller.

## 8. Difficulty

Per level. Every `retarget_window` finalized blocks (default 2016) the node compares the mean
mining time with the level's target block time (600 s at level 0, halving per level, floor 1 s)
and moves difficulty up or down by one leading zero (never below 0).

## 9. Chain verification

`verify_chain(chain)` re-checks, from the chain alone: genesis shape and hash; for every other
block its `tx_id`, uniqueness, `predecessor_*` links, state C, presence of a validator that
differs from the sender, signature, proof-of-work at `required_difficulty`, and that the
recorded balance fields match a running tally with no overdraft. `GET /verify` exposes it.

## 10. REST API

| Method | Path | Body / result |
|---|---|---|
| GET | `/status` | height, mempool size, counters, difficulty |
| GET | `/blockchain` | list of blocks |
| GET | `/mempool`, `/mempool/<tx_id>` | pending transactions |
| GET | `/balance/<address>` | `{balance, pending_outgoing}` |
| GET | `/verify` | `{ok, problems}` |
| GET | `/generate_keypair` | new keypair (convenience; clients should generate locally) |
| POST | `/create_transaction` | `{sender, receiver, amount, timestamp, signature}` -> 201 `{tx}` |
| POST | `/validate` | `{my_tx_id, target_tx_id}` -> `{my_tx, finalized}` |
| POST | `/advance_b`, `/advance_c` | 410 Gone |

Protocol rejections return HTTP 400 `{"error": <message>, "type": <exception class>}`.

## 11. Persistence

`Node(storage_path)` writes a JSON snapshot (`version`, `blockchain`, `mempool`, `stats`,
`difficulty`) atomically after every mutation and restores it on start.

## Open questions carried to later phases

- Real stability controller and burn rule (Phase 2).
- Bifurcation, layers, aggregation blocks, balance blocks (Phase 2 model, Phase 3 code).
- Size-scaled difficulty and validator counts; storage proof (Phase 3).
- Peer protocol and fork choice (Phase 3).
