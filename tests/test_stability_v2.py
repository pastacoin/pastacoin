import pytest

from pasta.sim import Shock, SimConfig, run_simulation
from pasta.stability import make_controller
from pasta.stability.controller import AnchoredSizeController, FlowPerUserController, PeriodAware


def _learn(ctrl, periods=5, amounts=(10.0, 20.0, 30.0), users=3, supply=1000.0):
    for _ in range(periods):
        ctrl.observe_period(list(amounts), users, supply)


def test_period_controllers_learn_anchor_then_act():
    c = AnchoredSizeController(learn_periods=5, alpha=1.0, gain=0.01, cap_rate=None, dispense="even")
    assert isinstance(c, PeriodAware)
    _learn(c)                                   # median 20 for 5 periods -> anchor 20
    assert c.anchor == pytest.approx(20.0)
    assert c.adjust(10.0) == 0.0                # nothing dispensed during learning
    c.observe_period([5.0, 10.0, 15.0], 3, 1000.0)   # median 10: signal -0.5 -> mint 0.5% of M = 5 over 3 txs
    assert c.signal() == pytest.approx(-0.5)
    assert c.adjust(1.0) == pytest.approx(5.0 / 3)
    assert c.adjust(1000.0) == pytest.approx(5.0 / 3)   # sizing independent of the carrier amount
    c.observe_period([30.0, 40.0, 50.0], 3, 1000.0)     # median 40: burn
    assert c.adjust(7.0) < 0


def test_cap_bounds_supply_change_per_period():
    c = AnchoredSizeController(anchor=20.0, alpha=1.0, gain=1.0, cap_rate=0.001, dispense="even", dust_fraction=0.0)
    c.observe_period([1.0, 1.0], 2, 1000.0)      # signal -0.95 -> uncapped delta 950, capped at 1
    assert c.adjust(1.0) == pytest.approx(0.5)
    assert c.adjust(999.0) == pytest.approx(0.5)


def test_proportional_dispensing_and_dust_floor():
    c = AnchoredSizeController(anchor=20.0, alpha=1.0, gain=0.01, cap_rate=None)   # proportional, dust 5% of running median
    c.observe_period([10.0, 10.0, 10.0], 3, 1000.0)                  # establishes the running median (10)
    c.observe_period([0.4, 0.4, 0.4, 10.0, 10.0, 10.0], 6, 1000.0)   # dust (< 0.5) ignored: median 10 -> mint 5 over flow 30
    assert c.signal() == pytest.approx(-0.5)
    assert c.adjust(10.0) == pytest.approx(5.0 * 10.0 / 30.0)
    assert c.adjust(0.4) == pytest.approx(5.0 * 0.4 / 30.0)          # dust gets a dust-sized share
    dusty = AnchoredSizeController(anchor=20.0, alpha=1.0, gain=0.01, cap_rate=None, dust_fraction=0.0)
    dusty.observe_period([10.0, 10.0, 10.0], 3, 1000.0)
    dusty.observe_period([0.4, 0.4, 0.4, 10.0, 10.0, 10.0], 6, 1000.0)  # no floor: median 5.2 -> stronger signal
    assert dusty.signal() < c.signal()


def test_flow_rule_uses_holders_not_active_addresses_by_default():
    c = FlowPerUserController(anchor=10.0, alpha=1.0, gain=0.01, cap_rate=None)
    c.observe_period([10.0] * 10, active_users=50, money_supply=1000.0, holders=10)   # 100 / 10 holders = anchor
    assert c.signal() == pytest.approx(0.0)
    a = FlowPerUserController(anchor=10.0, alpha=1.0, gain=0.01, cap_rate=None, users="active")
    a.observe_period([10.0] * 10, active_users=50, money_supply=1000.0, holders=10)   # 100 / 50 active = 2
    assert a.signal() == pytest.approx(-0.8)


def test_flow_per_user_ignores_granularity_but_sees_hoarding():
    c = FlowPerUserController(anchor=10.0, alpha=1.0, gain=0.01, cap_rate=None)
    c.observe_period([10.0] * 10, 10, 1000.0, holders=10)    # flow 100 / 10 holders = 10 = anchor
    assert c.signal() == pytest.approx(0.0)
    c.observe_period([20.0] * 5, 5, 1000.0, holders=10)      # fewer, larger, same total, fewer *active*: no signal
    assert c.signal() == pytest.approx(0.0)
    c.observe_period([5.0] * 10, 10, 1000.0, holders=10)     # flow halves (hoarding): mint
    assert c.signal() == pytest.approx(-0.5)
    assert c.adjust(3.0) > 0


def test_growth_allowance_moves_the_anchor():
    c = FlowPerUserController(anchor=10.0, learn_periods=0, alpha=1.0, gain=0.01, cap_rate=None, growth_per_period=0.1)
    c.observe_period([10.0] * 10, 10, 1000.0, holders=10)    # anchor now 11 -> stat 10 reads as -9%
    assert c.signal() == pytest.approx(10.0 / 11.0 - 1.0)
    assert c.adjust(1.0) > 0


def test_asymmetric_dispensing_targets_half_the_transactions():
    c = AnchoredSizeController(anchor=20.0, alpha=1.0, gain=0.01, cap_rate=None, asymmetric=True, dispense="even")
    c.observe_period([5.0, 10.0, 15.0], 3, 1000.0)   # mint: only txs >= median (10) get it, doubled
    assert c.adjust(12.0) == pytest.approx(2 * 5.0 / 3)
    assert c.adjust(8.0) == 0.0


def test_make_controller_round_two_names():
    assert isinstance(make_controller("size"), AnchoredSizeController)
    assert isinstance(make_controller("flow", gain=0.01), FlowPerUserController)


def _cfg(**kw):
    base = dict(agents=60, steps=800, warmup=100, seed=7)
    base.update(kw)
    return SimConfig(**base)


def test_wash_and_sybil_shocks_inflate_counts_not_supply():
    econ = run_simulation(_cfg(shocks=[Shock(300, "wash", 2), Shock(300, "sybil", 20)]))
    before = [r for r in econ.records if 200 <= r.step < 300]
    after = [r for r in econ.records if r.step >= 300]
    assert len(econ.wash_pairs) == 2 and len(econ.sybils) == 20
    assert sum(r.tx_count for r in after) / len(after) > 3 * sum(r.tx_count for r in before) / len(before)
    assert sum(r.active_users for r in after) / len(after) > 1.5 * sum(r.active_users for r in before) / len(before)
    m = econ.metrics()
    assert m["attacker_gain"] == pytest.approx(0.0, abs=1e-6)        # null controller: no mint to harvest
    assert econ.money_supply == pytest.approx(60 * 100.0)          # stake bought from honest agents
    assert m["price_drift_pct"] == pytest.approx(0.0, abs=1e-6)     # attackers add nothing real


def test_flow_controller_runs_in_economy_and_offsets_hoarding():
    shock = [Shock(300, "money_demand", 1.5)]
    null = run_simulation(_cfg(shocks=shock, steps=1500)).metrics()
    flow = run_simulation(_cfg(shocks=shock, steps=1500, controller="flow",
                               controller_kwargs=dict(learn_periods=100, gain=0.01, cap_rate=0.005))).metrics()
    assert abs(flow["price_drift_pct"]) < abs(null["price_drift_pct"])
    assert flow["total_minted"] > 0


def test_agents_shock_keeps_attacker_indices_valid():
    econ = run_simulation(_cfg(shocks=[Shock(200, "wash", 1), Shock(400, "agents", 30), Shock(600, "agents", -5)]))
    a, b = econ.wash_pairs[0]
    assert a >= econ.honest and b >= econ.honest and b < len(econ.balances)
    assert econ.honest == 85
