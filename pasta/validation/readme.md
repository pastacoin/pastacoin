# `pasta.validation`

* `engine.py` - performs transitions; does not decide whether they are allowed.
  `build_state_a`, `finalize_block` (B -> C: link, balances, validator, mine),
  `attach_validation_proof` (A -> B), `mine_pow` / `pow_is_valid`.
* `chain.py` - `verify_chain(chain)`: re-validates a chain from nothing but its contents and
  returns a list of problems (empty = consistent).

Difficulty is intentionally low; the prefix comes from the node per level.
