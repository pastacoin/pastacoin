"""The standard experiment matrix behind ``docs/SIMULATION-RESULTS.md`` and pastacoin.org/results.

Everything here is deterministic. ``run_all()`` returns plain dicts/lists so the result can be
dumped to JSON for the website and plotted for the memo (see :mod:`pasta.sim.report`).

Round one policies (per-transaction sizing):

* ``null``      - no mint or burn (baseline).
* ``trend``     - the whitepaper rule read literally (fast vs slow moving average of tx size,
                  asymmetric mint/burn), gain 0.5.
* ``anchored``  - the same asymmetric rule anchored to the launch-time average tx size,
                  gain 0.1 unless stated.

Round two policies (per-period, supply-fraction sizing, rate cap 0.05 % of supply per period,
proportional dispensing, dust floor; flow counts holders):

* ``size``      - median transaction size vs launch anchor.
* ``flow``      - nominal flow per active user vs launch anchor (growth allowance 0 unless stated).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List

from pasta.sim.economy import Economy, Shock, SimConfig

SHOCK_STEP = 2000
STEPS = 5000
SAMPLE_EVERY = 25

POLICIES = ["null", "trend", "anchored"]
POLICIES_V2 = ["null", "anchored", "size", "flow"]
POLICY_LABELS = {
    "null": "No controller",
    "trend": "Whitepaper rule (trend)",
    "anchored": "Anchored to launch average",
    "size": "Median size, supply-sized, capped",
    "flow": "Flow per user, supply-sized, capped",
}

SHOCKS = [
    ("none", "No shock", []),
    ("hoarding", "Hoarding: money demand x1.5", [Shock(SHOCK_STEP, "money_demand", 1.5)]),
    ("dishoarding", "Dishoarding: money demand x0.67", [Shock(SHOCK_STEP, "money_demand", 0.67)]),
    ("growth", "Real growth per capita x2", [Shock(SHOCK_STEP, "volume", 2.0)]),
    ("adoption", "Adoption: +200 agents with no coins", [Shock(SHOCK_STEP, "agents", 200)]),
    ("granularity_up", "Granularity x2: fewer, larger transactions", [Shock(SHOCK_STEP, "granularity", 2.0)]),
    ("granularity_down", "Granularity x0.5: more, smaller transactions", [Shock(SHOCK_STEP, "granularity", 0.5)]),
]

ATTACKS = [
    ("wash", "Wash trading: 5 pairs, 10 bounces per step", [Shock(SHOCK_STEP, "wash", 5)]),
    ("sybil", "Sybil: 200 fake addresses, 2 dust payments each per step", [Shock(SHOCK_STEP, "sybil", 200)]),
]

V2_DEFAULTS = {"learn_periods": 500, "alpha": 0.05, "gain": 0.002, "cap_rate": 0.0005}

# design-choice variants for the attack table
VARIANTS = [
    ("size_even", "size", {"dispense": "even"}, "Median size, even dispensing"),
    ("size_nodust", "size", {"dust_fraction": 0.0}, "Median size, no dust floor"),
    ("size", "size", {}, "Median size (proportional, dust floor)"),
    ("flow_active", "flow", {"users": "active"}, "Flow per active address"),
    ("flow_even", "flow", {"dispense": "even"}, "Flow per holder, even dispensing"),
    ("flow", "flow", {}, "Flow per holder (proportional, dust floor)"),
]


def launch_average(cfg: SimConfig) -> float:
    """Expected average transaction size at launch: M / (k * n * purchase probability)."""
    return cfg.agents * cfg.initial_balance / (cfg.money_demand * cfg.agents * cfg.buy_probability)


def base_config(**overrides) -> SimConfig:
    cfg = SimConfig(agents=200, steps=STEPS, seed=1, warmup=500)
    return replace(cfg, **overrides)


V2_MONEY_DEMAND = 100.0   # round two runs where agents hold ~10 payments, so affordability skips do not dominate


def base_config_v2(**overrides) -> SimConfig:
    return base_config(money_demand=V2_MONEY_DEMAND, **overrides)


def policy_config(policy: str, cfg: SimConfig, **params) -> SimConfig:
    if policy == "null":
        return replace(cfg, controller="null", controller_kwargs={})
    if policy == "trend":
        kw = {"gain": 0.5}
        kw.update(params)
        return replace(cfg, controller="trend", controller_kwargs=kw)
    if policy == "anchored":
        kw = {"target": launch_average(cfg), "gain": 0.1}
        kw.update(params)
        return replace(cfg, controller="fixed", controller_kwargs=kw)
    if policy in ("size", "flow"):
        kw = dict(V2_DEFAULTS)
        kw.update(params)
        return replace(cfg, controller=policy, controller_kwargs=kw)
    raise ValueError(policy)


def _series(econ: Economy, normalise_at: int) -> Dict[str, List[float]]:
    recs = econ.records
    ref = recs[normalise_at - 1].price_level if normalise_at > 0 else recs[0].price_level
    ref = ref or 1.0
    idx = list(range(0, len(recs), SAMPLE_EVERY))
    if idx[-1] != len(recs) - 1:
        idx.append(len(recs) - 1)
    return {
        "step": [recs[i].step for i in idx],
        "price_rel": [round(recs[i].price_level / ref, 4) for i in idx],
        "money_rel": [round(recs[i].money_supply / (recs[0].money_supply or 1.0), 4) for i in idx],
    }


def _run(cfg: SimConfig) -> Economy:
    return Economy(cfg).run()


def _summarise(econ: Economy, shocks) -> dict:
    m = econ.metrics()
    return {
        "series": _series(econ, SHOCK_STEP if shocks else 0),
        "drift_pct": round(m["price_drift_pct"], 2),
        "max_dev_pct": round(m["price_max_dev_pct"], 2),
        "money_change_pct": round(m["money_supply_change_pct"], 2),
        "recovery_steps": m["recovery_steps"],
        "minted": round(m["total_minted"], 1),
        "burned": round(m["total_burned"], 1),
        "attacker_gain": round(m["attacker_gain"], 1),
        "attacker_stake": round(m["attacker_stake"], 1),
    }


def _panel(cases, policies, base_fn=base_config) -> List[dict]:
    out = []
    for key, label, shocks in cases:
        base = base_fn(shocks=list(shocks))
        runs = {policy: _summarise(_run(policy_config(policy, base)), shocks) for policy in policies}
        out.append({"key": key, "label": label, "shock_step": SHOCK_STEP if shocks else None, "runs": runs})
    return out


def shocks_panel() -> List[dict]:
    return _panel(SHOCKS, POLICIES)


def shocks_panel_v2() -> List[dict]:
    return _panel(SHOCKS, POLICIES_V2, base_config_v2)


def attacks_panel() -> List[dict]:
    return _panel(ATTACKS, POLICIES_V2, base_config_v2)


def variants_table() -> List[dict]:
    """Design choices under the two attacks and the granularity shift: which knob fixes what."""
    cases = ATTACKS + [SHOCKS[5]]
    rows = []
    for vkey, policy, params, label in VARIANTS:
        row = {"key": vkey, "label": label}
        for ckey, _, shocks in cases:
            m = _run(policy_config(policy, base_config_v2(shocks=list(shocks)), **params)).metrics()
            row[ckey] = {"drift_pct": round(m["price_drift_pct"], 2), "attacker_gain": round(m["attacker_gain"], 1),
                         "attacker_stake": round(m["attacker_stake"], 1)}
        rows.append(row)
    return rows


def granularity_sweep(factors=(1.0, 1.25, 1.5, 2.0, 3.0, 4.0), money_demand: float = 100.0) -> dict:
    """Drift caused by a granularity shift alone (purchasing power is unchanged by construction).

    Uses a higher money demand than the default so agents hold ~10 purchases' worth and the
    affordability constraint does not dominate at large factors.
    """
    rows = []
    for f in factors:
        shocks = [] if f == 1.0 else [Shock(SHOCK_STEP, "granularity", f)]
        base = base_config(shocks=shocks, money_demand=money_demand)
        row = {"factor": f}
        for policy, params, name in (("null", {}, "null"), ("trend", {}, "trend"),
                                     ("anchored", {"gain": 0.1}, "anchored_g0.1"), ("anchored", {"gain": 0.5}, "anchored_g0.5"),
                                     ("size", {}, "size"), ("flow", {}, "flow")):
            m = _run(policy_config(policy, base, **params)).metrics()
            row[name] = {"drift_pct": round(m["price_drift_pct"], 2), "money_change_pct": round(m["money_supply_change_pct"], 2)}
        rows.append(row)
    return {"money_demand": money_demand, "rows": rows}


def gain_sweep(gains=(0.05, 0.1, 0.25, 0.5, 1.0)) -> List[dict]:
    rows = []
    base = base_config(shocks=[Shock(SHOCK_STEP, "money_demand", 1.5)])
    for g in gains:
        m = _run(policy_config("anchored", base, gain=g)).metrics()
        rows.append({
            "gain": g,
            "drift_pct": round(m["price_drift_pct"], 2),
            "recovery_steps": m["recovery_steps"],
            "minted": round(m["total_minted"], 1),
            "burned": round(m["total_burned"], 1),
            "churn": round(m["total_minted"] + m["total_burned"], 1),
        })
    return rows


CAP_SWEEP_GAIN = 0.01   # a gain high enough that the cap binds


def cap_sweep(caps=(None, 0.0002, 0.0005, 0.001, 0.002, 0.005)) -> List[dict]:
    """What the supply-rate cap buys. Median-size rule at gain 0.01 under (a) hoarding, where
    fast recovery is wanted, and (b) a sybil attack with the dust floor switched off, where the
    signal saturates and the cap is the only thing limiting the damage."""
    rows = []
    hoard = base_config_v2(shocks=[Shock(SHOCK_STEP, "money_demand", 1.5)])
    sybil = base_config_v2(shocks=[Shock(SHOCK_STEP, "sybil", 200)])
    for cap in caps:
        mh = _run(policy_config("size", hoard, cap_rate=cap, gain=CAP_SWEEP_GAIN)).metrics()
        ms = _run(policy_config("size", sybil, cap_rate=cap, gain=CAP_SWEEP_GAIN, dust_fraction=0.0)).metrics()
        rows.append({
            "cap_rate": cap,
            "hoarding_drift_pct": round(mh["price_drift_pct"], 2),
            "hoarding_recovery": mh["recovery_steps"],
            "hoarding_max_dev_pct": round(mh["price_max_dev_pct"], 2),
            "misread_drift_pct": round(ms["price_drift_pct"], 2),
            "misread_attacker_gain": round(ms["attacker_gain"], 1),
        })
    return rows


GROWTH_RATE = 0.0002   # steady per-capita real growth per step (x2.7 over the run)


def growth_allowance_sweep(allowances=(0.0, 0.0001, 0.0002, 0.0004)) -> List[dict]:
    """Steady real growth at GROWTH_RATE per step. The flow rule with a growth allowance equal
    to the true rate should hold the price level; with none it deflates at the growth rate;
    with too much it inflates. The size rule needs no allowance because the median falls with
    the price level. The no-growth column shows what each allowance costs when growth is absent."""
    rows = []
    grow = base_config_v2(real_growth_per_step=GROWTH_RATE)
    flat = base_config_v2()
    ms = _run(policy_config("size", grow)).metrics()
    mn = _run(policy_config("null", grow)).metrics()
    for a in allowances:
        mg = _run(policy_config("flow", grow, growth_per_period=a)).metrics()
        mf = _run(policy_config("flow", flat, growth_per_period=a)).metrics()
        rows.append({
            "growth_per_period": a,
            "flow_growth_drift_pct": round(mg["price_drift_pct"], 2),
            "flow_no_growth_drift_pct": round(mf["price_drift_pct"], 2),
            "size_growth_drift_pct": round(ms["price_drift_pct"], 2),
            "null_growth_drift_pct": round(mn["price_drift_pct"], 2),
        })
    return rows


def bias_panel() -> dict:
    """Steady-state drift with no shock at all: the controller acting on noise alone."""
    base = base_config()
    variants = {
        "trend_asymmetric": ("trend", {}),
        "trend_symmetric": ("trend", {"asymmetric": False}),
        "anchored": ("anchored", {}),
        "size": ("size", {}),
        "flow": ("flow", {}),
    }
    out = {}
    for key, (policy, params) in variants.items():
        econ = _run(policy_config(policy, base, **params))
        out[key] = {"series": _series(econ, 0), "drift_pct": round(econ.metrics()["price_drift_pct"], 2)}
    return out


def run_all() -> dict:
    cfg = base_config()
    return {
        "config": {
            "agents": cfg.agents, "steps": cfg.steps, "seed": cfg.seed, "money_demand": cfg.money_demand,
            "buy_probability": cfg.buy_probability, "real_price_sigma": cfg.real_price_sigma,
            "launch_average_tx": launch_average(cfg), "shock_step": SHOCK_STEP,
            "policies": POLICY_LABELS, "v2_defaults": V2_DEFAULTS, "v2_money_demand": V2_MONEY_DEMAND,
            "cap_sweep_gain": CAP_SWEEP_GAIN, "growth_rate": GROWTH_RATE,
        },
        "shocks": shocks_panel(),
        "granularity_sweep": granularity_sweep(),
        "gain_sweep": gain_sweep(),
        "bias": bias_panel(),
        "shocks_v2": shocks_panel_v2(),
        "attacks": attacks_panel(),
        "cap_sweep": cap_sweep(),
        "variants": variants_table(),
        "growth_allowance_sweep": growth_allowance_sweep(),
    }
