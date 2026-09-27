def test_zero_value_tx_mints_toward_target(node, wallet):
    sender, receiver = wallet(), wallet()
    tx = sender.send(node, receiver.pub, 0)
    assert tx["amount"] == 0.0          # signed amount is untouched
    assert tx["mint_amount"] == 10.0    # bootstrap mint fills the gap to the 10 PASTA target
    assert node._average_value() == 10.0

    # Once the average is at target, further zero-value txs mint nothing.
    tx2 = wallet().send(node, receiver.pub, 0)
    assert tx2["mint_amount"] == 0.0


def test_mint_is_credited_to_receiver_only(funded):
    node, rich, minter = funded["node"], funded["rich"], funded["minter"]
    assert node.balance_for(rich.pub) == 10.0
    assert node.balance_for(minter.pub) == 0.0
    finalized = node.get_blockchain()[2]
    assert finalized["sender_address"] == minter.pub
    assert finalized["receiver_balance_after"] == 10.0
    assert finalized["sender_balance_after"] == 0.0
