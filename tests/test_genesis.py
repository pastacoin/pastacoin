from pasta import Node


def test_genesis_block_and_mempool():
    """Ensure a fresh Node auto-creates genesis infrastructure."""
    node = Node()

    # Blockchain should contain exactly one block – the genesis block
    chain = node.get_blockchain()
    assert len(chain) == 1, "Blockchain should start with the genesis block"

    genesis = chain[0]
    assert genesis["sender_address"] == "GENESIS"
    assert genesis["receiver_address"] == "GENESIS"
    # Dataclass default state is "A"
    assert genesis.get("state", "A") == "A"

    # Mempool should contain the State-B genesis transaction
    mempool = node.get_mempool()
    assert len(mempool) == 1, "Mempool should contain the bootstrap transaction"
    gtx = mempool[0]
    assert gtx["state"] == "B", "Bootstrap transaction should be in State B"
    assert gtx["validated_block_id"] == genesis["block_hash"]
