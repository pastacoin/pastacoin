import copy

from conftest import P
from pasta import verify_chain


def _chain(funded, wallet):
    """genesis, bootstrap, helper's zero-amount block, then rich's 4 PASTA payment at index 3."""
    node, rich, helper, helper_tx = funded["node"], funded["rich"], funded["helper"], funded["helper_tx"]
    pay = rich.send(node, helper.pub, 4 * P)
    node.validate(pay["tx_id"], helper_tx["tx_id"])
    other = wallet().send(node, rich.pub, 0)
    node.validate(other["tx_id"], pay["tx_id"])
    chain = node.get_blockchain()
    assert len(chain) == 4 and verify_chain(chain) == []
    assert chain[3]["amount"] == 4 * P
    _chain_cache[0] = chain
    return chain


_chain_cache = [None]


def test_valid_chain_has_no_problems(funded, wallet):
    _chain(funded, wallet)


def test_tampered_amount_detected(funded, wallet):
    chain = copy.deepcopy(_chain(funded, wallet))
    chain[3]["amount"] = 9 * P
    problems = verify_chain(chain)
    assert any("tx_id" in p for p in problems)
    assert any("signature" in p for p in problems)
    assert any("proof-of-work" in p for p in problems)


def test_tampered_hash_breaks_link_and_pow(funded, wallet):
    chain = copy.deepcopy(_chain(funded, wallet))
    chain[2]["block_hash"] = "zz" + chain[2]["block_hash"][2:]
    problems = verify_chain(chain)
    assert any("block 2: proof-of-work" in p for p in problems)
    assert any("block 3: predecessor_hash" in p for p in problems)


def test_self_validation_detected(funded, wallet):
    chain = copy.deepcopy(_chain(funded, wallet))
    chain[3]["validator_address"] = chain[3]["sender_address"]
    problems = verify_chain(chain)
    assert any("self-validation" in p for p in problems)


def test_overdraft_and_balance_fields_detected(funded, wallet):
    chain = copy.deepcopy(_chain(funded, wallet))
    chain[3]["sender_balance_before"] = 99 * P
    problems = verify_chain(chain)
    assert any("sender_balance_before" in p for p in problems)


def test_reordered_blocks_detected(funded, wallet):
    chain = copy.deepcopy(_chain(funded, wallet))
    chain[2], chain[3] = chain[3], chain[2]
    assert verify_chain(chain)


def test_bad_genesis(funded, wallet):
    chain = copy.deepcopy(_chain(funded, wallet))
    chain[0]["amount"] = 1000 * P
    assert any("block 0: genesis amount" in p for p in verify_chain(chain))
    chain = copy.deepcopy(_chain_cache[0])
    chain[0]["receiver_address"] = "GENESIS"
    assert any("block 0: genesis must credit" in p for p in verify_chain(chain))
    assert verify_chain([]) == ["chain is empty"]
