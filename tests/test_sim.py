import pytest

from pasta.sim import Shock, SimConfig, run_simulation
from pasta.sim.__main__ import main as sim_main


def _cfg(**kw):
    base = dict(agents=60, steps=600, warmup=100, seed=7)
    base.update(kw)
    return SimConfig(**base)


def test_deterministic_and_money_conserved_without_controller():
    a = run_simulation(_cfg()).metrics()
    b = run_simulation(_cfg()).metrics()
    assert a == b
    econ = run_simulation(_cfg())
    assert econ.money_supply == pytest.approx(60 * 100.0)        # null controller: M constant
    assert econ.metrics()["price_drift_pct"] == pytest.approx(0.0)


def test_money_demand_shock_is_deflationary_without_controller():
    cfg = _cfg(shocks=[Shock(300, "money_demand", 2.0)])
    m = run_simulation(cfg).metrics()
    assert m["price_drift_pct"] < -40          # p halves when k doubles


def test_controller_offsets_money_demand_shock():
    shock = [Shock(300, "money_demand", 1.5)]
    null = run_simulation(_cfg(shocks=shock)).metrics()
    trend = run_simulation(_cfg(shocks=shock, controller="trend", steps=1500,
                                controller_kwargs=dict(gain=1.0, max_fraction=0.2))).metrics()
    assert abs(trend["price_drift_pct"]) < abs(null["price_drift_pct"])
    assert trend["total_minted"] > 0


def test_agents_shock_and_csv(tmp_path):
    econ = run_simulation(_cfg(shocks=[Shock(200, "agents", 20), Shock(400, "agents", -5)]))
    assert len(econ.balances) == 75
    out = tmp_path / "run.csv"
    econ.write_csv(str(out))
    assert out.read_text().startswith("step,price_level,")


def test_granularity_shock_keeps_price_level_but_doubles_average_tx():
    econ = run_simulation(_cfg(shocks=[Shock(300, "granularity", 2.0)]))
    before = [r for r in econ.records if 100 <= r.step < 300]
    after = [r for r in econ.records if r.step >= 300]
    assert econ.metrics()["price_drift_pct"] == pytest.approx(0.0)   # purchasing power unchanged
    avg_before = sum(r.tx_volume_pasta for r in before) / sum(r.tx_count for r in before)
    avg_after = sum(r.tx_volume_pasta for r in after) / sum(r.tx_count for r in after)
    # Not a clean 2x: larger purchases are skipped more often when unaffordable, which
    # biases the observed average down. Still clearly a jump with no change in p.
    assert avg_after > 1.4 * avg_before


def test_recovery_steps_metric():
    cfg = _cfg(shocks=[Shock(300, "money_demand", 1.5)], controller="fixed", steps=3000,
               controller_kwargs=dict(target=50.0, gain=0.25))
    m = run_simulation(cfg).metrics()
    assert m["recovery_steps"] is not None and 0 < m["recovery_steps"] < 2500
    assert run_simulation(_cfg()).metrics()["recovery_steps"] is None
    assert run_simulation(_cfg(shocks=[Shock(300, "money_demand", 2.0)])).metrics()["recovery_steps"] is None


def test_shock_parse_and_unknown_kind():
    s = Shock.parse("2000:volume:2.5")
    assert (s.step, s.kind, s.factor) == (2000, "volume", 2.5)
    with pytest.raises(ValueError):
        run_simulation(_cfg(shocks=[Shock(1, "weather", 2.0)]))


def test_cli_compare_runs(capsys):
    assert sim_main(["--compare", "--agents", "40", "--steps", "300", "--shock", "150:money_demand:1.3"]) == 0
    out = capsys.readouterr().out
    assert "null" in out and "trend" in out and "fixed" in out


def test_cold_start_launch_rule_reaches_the_declared_target():
    from pasta.sim.experiments import cold_start_run
    kw = dict(doubling=200, limit=150, steps=2500)
    launch = cold_start_run("size", **kw)
    nothing = cold_start_run("null", **kw)
    assert launch["users"] > 100
    assert launch["steps_to_target"] is not None
    assert 0.8 < launch["level_vs_target_final"] < 1.2        # the price level sits on the declared target
    assert launch["first_users_share"] < 0.25                 # the first ten users do not end up owning it
    assert nothing["steps_to_target"] is None and nothing["level_vs_target_final"] < 0.05
    slow = cold_start_run("size", bootstrap_cap_rate=None, **kw)   # mature cap only
    assert slow["steps_to_target"] is None or slow["steps_to_target"] > launch["steps_to_target"]
