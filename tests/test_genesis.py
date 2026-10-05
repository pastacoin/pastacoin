import pytest

from pasta import InvalidTransaction, Node
from pasta.core.units import UNITS_PER_PASTA


def test_genesis_block_credits_the_first_address_and_bootstrap_mempool(node, founder):
    chain = node.get_blockchain()
    assert len(chain) == 1
    genesis = chain[0]
    assert genesis["sender_address"] == "GENESIS"
    assert genesis["receiver_address"] == founder.pub
    assert genesis["amount"] == 10 * UNITS_PER_PASTA
    assert genesis["state"] == "C"
    assert genesis["block_hash"]
    assert node.balance_for(founder.pub) == 10 * UNITS_PER_PASTA
    assert node.status()["stability"]["supply"] == 10 * UNITS_PER_PASTA

    mempool = node.get_mempool()
    assert len(mempool) == 1
    bootstrap = mempool[0]
    assert bootstrap["state"] == "B"
    assert bootstrap["sender_address"] == "GENESIS" and bootstrap["amount"] == 0
    assert bootstrap["validated_block_id"] == genesis["tx_id"]
    assert bootstrap["validated_block_hash"] == genesis["block_hash"]


def test_fresh_node_verifies_clean(node):
    assert node.verify() == []


def test_a_new_chain_needs_a_genesis_receiver():
    with pytest.raises(ValueError, match="genesis_receiver"):
        Node()


def test_nobody_can_send_as_genesis(node, wallet):
    with pytest.raises(InvalidTransaction, match="GENESIS"):
        node.create_transaction("GENESIS", wallet().pub, 5 * UNITS_PER_PASTA)
