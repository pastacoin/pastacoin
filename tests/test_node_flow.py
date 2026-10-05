import pytest

from conftest import P
from pasta import (
    InsufficientBalance,
    InvalidSignature,
    InvalidTransaction,
    InvalidTransition,
    Node,
    NotFound,
)


def test_full_a_b_c_flow(node, wallet, bootstrap_id):
    alice, bob = wallet(), wallet()

    # Alice creates a zero-value tx (State A) and validates the bootstrap tx.
    a_tx = alice.send(node, bob.pub, 0)
    assert a_tx["state"] == "A"
    result = node.validate(a_tx["tx_id"], bootstrap_id)
    assert result["my_tx"]["state"] == "B"
    assert result["my_tx"]["validated_block_id"] == bootstrap_id
    assert result["finalized"]["state"] == "C"
    assert result["finalized"]["validator_address"] == alice.pub
    assert len(node.get_blockchain()) == 2
    assert node.get_mempool()[0]["tx_id"] == a_tx["tx_id"]

    # Bob creates a tx and validates Alice's, which finalizes it with Bob as validator.
    b_tx = bob.send(node, alice.pub, 0)
    result = node.validate(b_tx["tx_id"], a_tx["tx_id"])
    fin = result["finalized"]
    assert fin["tx_id"] == a_tx["tx_id"]
    assert fin["validator_address"] == bob.pub
    assert fin["predecessor_hash"] == node.get_blockchain()[1]["block_hash"]
    assert node.balance_for(bob.pub) == 0          # zero-amount transactions move and mint nothing
    assert node.verify() == []


def test_self_validation_rejected(node, wallet, bootstrap_id):
    alice = wallet()
    t1 = alice.send(node, alice.pub, 0)
    node.validate(t1["tx_id"], bootstrap_id)          # t1 -> B
    t2 = alice.send(node, alice.pub, 0)
    with pytest.raises(InvalidTransition, match="self-validation"):
        node.validate(t2["tx_id"], t1["tx_id"])
    with pytest.raises(InvalidTransition, match="itself"):
        node.validate(t2["tx_id"], t2["tx_id"])


def test_only_state_b_targets_are_eligible(node, wallet):
    alice, bob = wallet(), wallet()
    a = alice.send(node, bob.pub, 0)
    b = bob.send(node, alice.pub, 0)
    with pytest.raises(InvalidTransition, match="state A"):
        node.validate(a["tx_id"], b["tx_id"])


def test_state_b_cannot_validate_again(node, wallet, bootstrap_id):
    alice, bob = wallet(), wallet()
    a = alice.send(node, bob.pub, 0)
    node.validate(a["tx_id"], bootstrap_id)
    b = bob.send(node, alice.pub, 0)
    node.validate(b["tx_id"], a["tx_id"])
    # b is now in state B and nothing eligible remains; b cannot validate anything more
    c = alice.send(node, bob.pub, 0)
    with pytest.raises(InvalidTransition, match="only state A"):
        node.validate(b["tx_id"], c["tx_id"])


def test_unsigned_and_badly_signed_rejected(node, wallet):
    alice, bob = wallet(), wallet()
    with pytest.raises(InvalidSignature):
        alice.send(node, bob.pub, 0, signature="")
    good_sig_other_amount = None
    ts = alice.next_timestamp()
    from pasta import sign_transaction
    good_sig_other_amount = sign_transaction(alice.priv, alice.pub, bob.pub, P, ts)
    with pytest.raises(InvalidSignature):
        alice.send(node, bob.pub, 2 * P, timestamp=ts, signature=good_sig_other_amount)
    # signing key does not belong to the claimed sender
    with pytest.raises(InvalidSignature):
        node.create_transaction(bob.pub, alice.pub, 0, timestamp=ts,
                                signature=sign_transaction(alice.priv, bob.pub, alice.pub, 0, ts))


def test_signatures_can_be_disabled_for_experiments():
    node = Node(genesis_receiver="founder", require_signatures=False)
    tx = node.create_transaction("anyone", "someone", 0)
    assert tx["state"] == "A"


def test_overdraft_rejected_at_creation(funded):
    node, rich, helper = funded["node"], funded["rich"], funded["helper"]
    with pytest.raises(InsufficientBalance):
        helper.send(node, rich.pub, P)                # helper has 0
    with pytest.raises(InsufficientBalance):
        rich.send(node, helper.pub, 10 * P + 1)       # rich has exactly 10 PASTA
    ok = rich.send(node, helper.pub, 6 * P)
    with pytest.raises(InsufficientBalance):
        rich.send(node, helper.pub, 5 * P)            # 10 - 6 pending = 4 available
    assert ok["state"] == "A"


def test_spend_flow_updates_balances(funded, wallet):
    node, rich, helper, helper_tx = funded["node"], funded["rich"], funded["helper"], funded["helper_tx"]
    pay = rich.send(node, helper.pub, 4 * P)
    node.validate(pay["tx_id"], helper_tx["tx_id"])    # pay -> B, helper_tx finalized
    other = wallet().send(node, rich.pub, 0)
    node.validate(other["tx_id"], pay["tx_id"])        # pay finalized by a third party
    assert node.balance_for(rich.pub) == 6 * P
    assert node.balance_for(helper.pub) == 4 * P
    assert node.verify() == []


def test_duplicate_and_bad_inputs(node, wallet):
    alice, bob = wallet(), wallet()
    ts = alice.next_timestamp()
    alice.send(node, bob.pub, 0, timestamp=ts)
    with pytest.raises(InvalidTransaction, match="duplicate"):
        alice.send(node, bob.pub, 0, timestamp=ts)
    with pytest.raises(InvalidTransaction):
        alice.send(node, bob.pub, -1)
    with pytest.raises(InvalidTransaction, match="whole number"):
        node.create_transaction(alice.pub, bob.pub, 1.5, timestamp=ts + 1, signature="x")
    with pytest.raises(InvalidTransaction):
        node.create_transaction("", bob.pub, 0)
    with pytest.raises(NotFound):
        node.validate("nope", "nada")
    with pytest.raises(NotFound):
        node.get_mempool_tx("nope")


def test_status_reports_shape(node):
    s = node.status()
    assert s["height"] == 1 and s["mempool_size"] == 1
    assert s["require_signatures"] is True and s["persistent"] is False
    assert s["units_per_pasta"] == P and s["stability"]["supply"] == 10 * P
