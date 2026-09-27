from pasta import Node


def test_genesis_block_and_bootstrap_mempool():
    node = Node()

    chain = node.get_blockchain()
    assert len(chain) == 1
    genesis = chain[0]
    assert genesis["sender_address"] == "GENESIS"
    assert genesis["receiver_address"] == "GENESIS"
    assert genesis["state"] == "C"
    assert genesis["block_hash"]

    mempool = node.get_mempool()
    assert len(mempool) == 1
    bootstrap = mempool[0]
    assert bootstrap["state"] == "B"
    assert bootstrap["sender_address"] == "GENESIS"
    assert bootstrap["validated_block_id"] == genesis["tx_id"]
    assert bootstrap["validated_block_hash"] == genesis["block_hash"]


def test_fresh_node_verifies_clean():
    assert Node().verify() == []
