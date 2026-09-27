import pytest

from pasta.stability import FixedTargetController, NullController, TrendController, make_controller


def test_null_controller_does_nothing():
    c = NullController()
    assert [c.adjust(x) for x in (1, 5, 100)] == [0.0, 0.0, 0.0]
    assert c.signal() == 0.0


def test_fixed_target_mints_when_average_low_and_burns_when_high():
    c = FixedTargetController(target=10.0, alpha=1.0, gain=1.0, max_fraction=0.5, asymmetric=False)
    assert c.adjust(5.0) > 0          # avg 5 < 10 -> mint
    assert c.adjust(20.0) < 0         # avg 20 > 10 -> burn
    c2 = FixedTargetController(target=10.0, alpha=1.0, gain=1.0, max_fraction=0.5, asymmetric=False)
    assert c2.adjust(10.0) == 0.0     # on target


def test_asymmetry_rule_from_whitepaper():
    # average is low (deflation) -> only transactions at/above the average receive mint
    c = FixedTargetController(target=100.0, alpha=0.5, gain=1.0, max_fraction=0.5)
    c.adjust(10.0)                    # avg = 10
    assert c.adjust(5.0) == 0.0       # below average: no mint
    assert c.adjust(50.0) > 0.0       # above average: mint
    # average is high (inflation) -> only transactions at/below the average are burned
    c = FixedTargetController(target=1.0, alpha=0.5, gain=1.0, max_fraction=0.5)
    c.adjust(10.0)
    assert c.adjust(50.0) == 0.0
    assert c.adjust(2.0) < 0.0


def test_adjustment_is_capped():
    c = FixedTargetController(target=1000.0, alpha=1.0, gain=10.0, max_fraction=0.1, asymmetric=False)
    assert c.adjust(10.0) == pytest.approx(1.0)   # 10% cap


def test_trend_controller_reacts_to_change_not_level():
    c = TrendController(fast_alpha=0.5, slow_alpha=0.01, gain=1.0, max_fraction=0.5, asymmetric=False)
    for _ in range(200):
        c.adjust(10.0)
    assert abs(c.signal()) < 1e-6 and abs(c.adjust(10.0)) < 1e-6   # flat -> no action at any level
    adj = c.adjust(20.0)                                              # jump up -> burn
    assert adj < 0 and c.signal() > 0


def test_make_controller():
    assert isinstance(make_controller("null"), NullController)
    assert isinstance(make_controller("fixed", target=5.0), FixedTargetController)
    assert isinstance(make_controller("trend"), TrendController)
    with pytest.raises(ValueError):
        make_controller("banana")
