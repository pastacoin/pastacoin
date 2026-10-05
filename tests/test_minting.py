"""The launch mint rule on the chain (docs/SPEC.md section 7, issue #40)."""
import copy

import pytest

from conftest import P, Wallet, pay
from pasta import Node, verify_chain
from pasta.stability.chain import ChainStability, StabilityParams, replay

FAST = StabilityParams(period_payments=2)     # a period every two payments


@pytest.fixture
def fast_node(founder):
    return Node(genesis_receiver=founder.pub, stability_params=FAST)


def test_first_period_mints_nothing(fast_node, founder, wallet):
    bob = wallet()
    b1 = pay(fast_node, founder, bob.pub, P)
    b2 = pay(fast_node, founder, bob.pub, P)
    assert b1["mint_amount"] == 0 and b2["mint_amount"] == 0
    s = fast_node.status()["stability"]
    assert s["period"] == 1 and s["supply"] == 10 * P
    # median payment 1 PASTA against a 10 PASTA target: signal -0.9, so the rule wants
    # 0.02 * 0.9 = 1.8 % of the 10 PASTA supply minted over the next period
    assert s["signal"] == pytest.approx(-0.9)
    assert s["period_budget"] == pytest.approx(0.18 * P, abs=2)


def test_budget_is_shared_in_proportion_and_credited_to_the_receiver(fast_node, founder, wallet):
    bob = wallet()
    pay(fast_node, founder, bob.pub, P)
    pay(fast_node, founder, bob.pub, P)
    budget = fast_node.status()["stability"]["period_budget"]

    b3 = pay(fast_node, founder, bob.pub, P)        # half of the previous period's flow
    assert b3["mint_amount"] == budget // 2
    assert b3["receiver_balance_after"] - b3["receiver_balance_before"] == P + budget // 2
    assert b3["sender_balance_before"] - b3["sender_balance_after"] == P      # the sender pays only the amount
    assert fast_node.balance_for(bob.pub) == 3 * P + budget // 2
    assert fast_node.status()["stability"]["supply"] == 10 * P + budget // 2
    assert fast_node.verify() == []


def test_a_large_payment_cannot_mint_more_than_the_period_budget(fast_node, founder, wallet):
    bob = wallet()
    pay(fast_node, founder, bob.pub, P // 100)      # a quiet period: two payments of 0.01
    pay(fast_node, founder, bob.pub, P // 100)
    budget = fast_node.status()["stability"]["period_budget"]
    assert budget > 0
    big = pay(fast_node, founder, bob.pub, 5 * P)   # 250x the previous period's flow
    assert big["mint_amount"] == budget
    assert fast_node.status()["stability"]["period_remaining"] == 0
    nxt = pay(fast_node, founder, bob.pub, P)       # budget spent: nothing left this period
    assert nxt["mint_amount"] == 0


def test_zero_amount_blocks_carry_no_mint_and_are_not_counted(fast_node, founder, wallet):
    bob = wallet()
    pay(fast_node, founder, bob.pub, P)
    pay(fast_node, founder, bob.pub, P)
    assert fast_node.status()["stability"]["period_budget"] > 0
    for block in fast_node.get_blockchain()[1:]:
        if block["amount"] == 0:
            assert block["mint_amount"] == 0
    # four zero-amount helper blocks and the bootstrap did not advance the period
    assert fast_node.status()["stability"]["period"] == 1


def test_self_payments_are_rejected(node, founder):
    from pasta import InvalidTransaction
    with pytest.raises(InvalidTransaction, match="differ"):
        founder.send(node, founder.pub, P)


def test_burns_when_payments_run_above_target(founder, wallet):
    params = StabilityParams(period_payments=2, target_median=P // 10)   # target 0.1 PASTA
    node = Node(genesis_receiver=founder.pub, stability_params=params)
    bob = wallet()
    pay(node, founder, bob.pub, P)
    pay(node, founder, bob.pub, P)
    s = node.status()["stability"]
    assert s["signal"] > 0
    assert s["period_budget"] == pytest.approx(-0.2 * P, abs=2)            # capped burn: 2 % of supply
    b = pay(node, founder, bob.pub, P)
    assert b["mint_amount"] == -((-s["period_budget"]) // 2)
    assert b["receiver_balance_after"] - b["receiver_balance_before"] == P + b["mint_amount"]
    assert node.status()["stability"]["supply"] == 10 * P + b["mint_amount"]
    assert node.status()["stability"]["burned"] == -b["mint_amount"]
    assert node.verify() == []


def test_verify_chain_recomputes_every_mint(fast_node, founder, wallet):
    bob = wallet()
    for _ in range(5):
        pay(fast_node, founder, bob.pub, P)
    chain = fast_node.get_blockchain()
    assert verify_chain(chain, FAST) == []
    assert any(b["mint_amount"] > 0 for b in chain)

    forged = copy.deepcopy(chain)
    minted = next(i for i, b in enumerate(forged) if b["mint_amount"] > 0)
    forged[minted]["mint_amount"] += 1
    assert any("mint_amount" in p for p in verify_chain(forged, FAST))

    # the same chain judged under different rule constants does not verify either
    assert any("mint_amount" in p for p in verify_chain(chain))


def test_replay_matches_the_live_rule_and_survives_a_restart(tmp_path, founder, wallet):
    path = tmp_path / "node.json"
    node = Node(str(path), genesis_receiver=founder.pub, stability_params=FAST)
    bob = wallet()
    for _ in range(5):
        pay(node, founder, bob.pub, P)
    live = node.status()["stability"]
    assert replay(node.get_blockchain(), FAST).status() == live
    assert Node(str(path), stability_params=FAST).status()["stability"] == live


def test_supply_equals_the_sum_of_balances(fast_node, founder, wallet):
    bob, carol = wallet(), wallet()
    for _ in range(4):
        pay(fast_node, founder, bob.pub, P)
    pay(fast_node, bob, carol.pub, P // 2)
    pay(fast_node, bob, carol.pub, P // 2)
    total = sum(fast_node.balance_for(w.pub) for w in (founder, bob, carol))
    assert total == fast_node.status()["stability"]["supply"]
    assert fast_node.status()["stability"]["minted"] == total - 10 * P


def test_cap_tapers_above_the_bootstrap_supply():
    rule = ChainStability(StabilityParams(bootstrap_supply=100 * P))
    rule.supply = 50 * P
    assert rule.status()["cap_rate"] == pytest.approx(0.02)
    rule.supply = 400 * P
    assert rule.status()["cap_rate"] == pytest.approx(0.005)
    rule.supply = 100_000 * P
    assert rule.status()["cap_rate"] == pytest.approx(0.002)      # the mature cap is the floor
