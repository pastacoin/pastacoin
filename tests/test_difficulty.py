from pasta import Node


def test_difficulty_rises_when_blocks_are_fast_and_falls_when_slow():
    node = Node(retarget_window=3, target_block_time=10.0)
    assert node.difficulty_for_level(0) == 0

    for _ in range(3):
        node._record_block_time(0, 1.0)      # much faster than 10s target
    assert node.difficulty_for_level(0) == 1

    for _ in range(3):
        node._record_block_time(0, 0.5)
    assert node.difficulty_for_level(0) == 2

    for _ in range(3):
        node._record_block_time(0, 50.0)     # far slower than target
    assert node.difficulty_for_level(0) == 1

    for _ in range(6):
        node._record_block_time(0, 50.0)
    assert node.difficulty_for_level(0) == 0  # never below zero


def test_higher_levels_have_shorter_targets():
    node = Node(target_block_time=600.0)
    assert node._target_block_time_for_level(0) == 600.0
    assert node._target_block_time_for_level(1) == 300.0
    assert node._target_block_time_for_level(20) == 1.0


def test_new_transactions_carry_current_difficulty(node, wallet):
    node._difficulty_by_level[0] = 2
    tx = wallet().send(node, wallet().pub, 0)
    assert tx["required_difficulty"] == 2
    bootstrap = node.get_mempool()[0]["tx_id"]
    result = node.validate(tx["tx_id"], bootstrap)
    fin = result["finalized"]
    assert fin["required_difficulty"] == 2
    assert fin["block_hash"].startswith("00")
    assert node.verify() == []
