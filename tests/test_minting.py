from pasta import Node


def test_zero_value_mints():
    node = Node()
    sender = "SENDER"
    receiver = "RECV"

    # first tx zero-value should mint 10
    tx = node.create_transaction(sender, receiver, 0)
    assert tx["amount"] > 0
    assert tx["mint_amount"] == tx["amount"]

    # average should now equal minted amount
    assert node._average_amount() == tx["amount"]
