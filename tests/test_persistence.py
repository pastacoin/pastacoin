import json

from pasta import Node


def test_snapshot_roundtrip(tmp_path, wallet):
    path = tmp_path / "state" / "node.json"
    node = Node(str(path))
    bootstrap = node.get_mempool()[0]["tx_id"]
    alice, bob = wallet(), wallet()
    a = alice.send(node, bob.pub, 0)
    node.validate(a["tx_id"], bootstrap)
    b = bob.send(node, alice.pub, 0)

    assert path.exists()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1 and len(raw["blockchain"]) == 2

    reloaded = Node(str(path))
    assert reloaded.get_blockchain() == node.get_blockchain()
    assert reloaded.get_mempool() == node.get_mempool()
    assert reloaded.tx_counter == node.tx_counter
    assert reloaded.total_value == node.total_value
    assert reloaded.verify() == []

    # the reloaded node continues the same history
    reloaded.validate(b["tx_id"], a["tx_id"])
    assert len(reloaded.get_blockchain()) == 3
    assert reloaded.balance_for(bob.pub) == 10.0


def test_reload_does_not_recreate_bootstrap_after_it_was_consumed(tmp_path, wallet):
    path = tmp_path / "node.json"
    node = Node(str(path))
    bootstrap = node.get_mempool()[0]["tx_id"]
    a = wallet().send(node, wallet().pub, 0)
    node.validate(a["tx_id"], bootstrap)
    # mempool now holds only a; chain height 2
    reloaded = Node(str(path))
    assert [t["tx_id"] for t in reloaded.get_mempool()] == [a["tx_id"]]
