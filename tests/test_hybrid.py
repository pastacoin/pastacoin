import pytest

from pasta.sim import Shock, SimConfig, run_simulation
from pasta.stability import HybridController, make_controller


def _ctrl(**kw):
    base = dict(anchor=10.0, flow_anchor=10.0, alpha=1.0, slow_alpha=0.0, gain=0.01, cap_rate=None,
                step_threshold=0.15, settle_periods=3, settle_tolerance=0.05)
    base.update(kw)
    return HybridController(**base)


def _warm(c, periods=3):
    for _ in range(periods):
        c.observe_period([10.0] * 10, 10, 1000.0, holders=10)     # median 10, flow/holder 10


def test_step_in_median_with_flat_flow_reanchors_and_does_not_act():
    c = _ctrl()
    _warm(c)
    # granularity x2: 5 payments of 20 instead of 10 of 10; flow per holder unchanged
    c.observe_period([20.0] * 5, 5, 1000.0, holders=10)
    assert c.in_step and c.reanchors == 0
    assert abs(c.signal()) < 1e-9                      # during the step: act on the flow part, which is zero
    assert c.adjust(20.0) == pytest.approx(0.0, abs=1e-9)
    for _ in range(3):                                 # settles
        c.observe_period([20.0] * 5, 5, 1000.0, holders=10)
    assert not c.in_step and c.reanchors == 1
    assert c.anchor == pytest.approx(20.0)
    assert abs(c.signal()) < 1e-9


def test_step_matched_by_flow_acts_without_reanchoring():
    c = _ctrl()
    _warm(c)
    # hoarding: everything halves, flow per holder halves too
    c.observe_period([5.0] * 10, 10, 1000.0, holders=10)
    assert c.in_step
    assert c.signal() == pytest.approx(-0.5)           # monetary part acted on immediately
    assert c.adjust(5.0) > 0
    for _ in range(3):
        c.observe_period([5.0] * 10, 10, 1000.0, holders=10)
    assert not c.in_step and c.reanchors == 0          # nothing structural: anchor untouched
    assert c.anchor == pytest.approx(10.0)
    assert c.signal() == pytest.approx(-0.5)


def test_recovery_after_a_monetary_step_keeps_minting():
    c = _ctrl()
    _warm(c)
    for _ in range(4):
        c.observe_period([5.0] * 10, 10, 1000.0, holders=10)     # hoarding step, settles, no re-anchor
    assert not c.in_step and c.anchor == pytest.approx(10.0)
    # recovery in progress: median and flow both back to 8; a new step opens (8/5 > 15%)
    for _ in range(4):
        c.observe_period([8.0] * 10, 10, 1000.0, holders=10)
    assert c.signal() == pytest.approx(-0.2)                     # still below the launch anchors: keep minting
    assert c.anchor == pytest.approx(10.0)                       # recovery is not structure


def test_combined_step_is_split():
    c = _ctrl()
    _warm(c)
    # hoarding (x0.5) and granularity x2 at once: median unchanged (10), flow per holder halves
    c.observe_period([10.0] * 5, 5, 1000.0, holders=10)
    assert not c.in_step and c.reanchors == 0            # no step in the median: nothing to decompose
    # median x2 while flow per holder falls to 0.4x: structural part is x5, monetary part is x0.4
    c2 = _ctrl()
    _warm(c2)
    for _ in range(4):
        c2.observe_period([20.0] * 2, 2, 1000.0, holders=10)   # flow per holder 40/10 = 4
    assert c2.reanchors == 1
    assert c2.anchor == pytest.approx(10.0 * 2.0 / 0.4)        # 50
    assert c2.signal() == pytest.approx(20.0 / 50.0 - 1.0)     # remaining monetary part: -60% -> mint


def test_slow_drift_passes_through_to_the_size_signal():
    c = _ctrl(alpha=0.5, slow_alpha=0.5)   # fast == slow: a drift never looks like a step
    _warm(c)
    for k in range(40):                     # median drifts down 1% per period, flow flat
        m = 10.0 * (0.99 ** (k + 1))
        c.observe_period([m] * 10, 10, 1000.0, holders=10)
    assert c.reanchors == 0
    assert c.signal() < -0.2
    assert c.adjust(5.0) > 0


def test_make_controller_hybrid():
    assert isinstance(make_controller("hybrid"), HybridController)


def _cfg(**kw):
    base = dict(agents=60, steps=1800, warmup=100, seed=7, money_demand=100.0)
    base.update(kw)
    return SimConfig(**base)


HY = dict(learn_periods=200, alpha=0.05, gain=0.002, cap_rate=0.0005)


def test_flow_reference_drifts_only_when_calm():
    c = _ctrl(slow_alpha=0.5, calm_tolerance=0.15)
    _warm(c)
    for _ in range(3):
        c.observe_period([10.0] * 10, 10, 1000.0, holders=12)   # flow per holder 8.3, median at anchor: calm
    assert c.flow_anchor < 10.0                                 # reference followed
    d = _ctrl(slow_alpha=0.5, calm_tolerance=0.15)
    _warm(d)
    for _ in range(3):
        d.observe_period([6.0] * 10, 10, 1000.0, holders=12)    # median 40% below anchor: not calm
    assert d.flow_anchor == pytest.approx(10.0)                 # reference frozen


def test_hybrid_in_economy_handles_hoarding_and_granularity():
    hoard = [Shock(600, "money_demand", 1.5)]
    gran = [Shock(600, "granularity", 2.0)]
    null_h = run_simulation(_cfg(shocks=hoard)).metrics()
    hy_h = run_simulation(_cfg(shocks=hoard, controller="hybrid", controller_kwargs=HY)).metrics()
    size_g = run_simulation(_cfg(shocks=gran, controller="size", controller_kwargs=HY)).metrics()
    hy_g = run_simulation(_cfg(shocks=gran, controller="hybrid", controller_kwargs=HY)).metrics()
    assert abs(hy_h["price_drift_pct"]) < abs(null_h["price_drift_pct"]) * 0.5
    assert abs(hy_g["price_drift_pct"]) < abs(size_g["price_drift_pct"]) * 0.5
