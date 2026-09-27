"""The standard experiment matrix behind ``docs/SIMULATION-RESULTS.md`` and pastacoin.org/results.

Everything here is deterministic. ``run_all()`` returns plain dicts/lists so the result can be
dumped to JSON for the website and plotted for the memo (see :mod:`pasta.sim.report`).

Three policies are compared throughout:

* ``null``      - no mint or burn (baseline).
* ``trend``     - the whitepaper rule read literally (fast vs slow moving average of tx size,
                  asymmetric mint/burn), gain 0.5.
* ``anchored``  - the same asymmetric rule anchored to the launch-time average tx size,
                  gain 0.1 unless stated.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List

from pasta.sim.economy import Economy, Shock, SimConfig

SHOCK_STEP = 2000
STEPS = 5000
SAMPLE_EVERY = 25

POLICIES = ["null", "trend", "anchored"]
POLICY_LABELS = {
    "null": "No controller",
    "trend": "Whitepaper rule (trend)",
    "anchored": "Anchored to launch average",
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


def launch_average(cfg: SimConfig) -> float:
    """Expected average transaction size at launch: M / (k * n * purchase probability)."""
    return cfg.agents * cfg.initial_balance / (cfg.money_demand * cfg.agents * cfg.buy_probability)


def base_config(**overrides) -> SimConfig:
    cfg = SimConfig(agents=200, steps=STEPS, seed=1, warmup=500)
    return replace(cfg, **overrides)


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


def shocks_panel() -> List[dict]:
    out = []
    for key, label, shocks in SHOCKS:
        base = base_config(shocks=list(shocks))
        runs = {}
        for policy in POLICIES:
            econ = _run(policy_config(policy, base))
            m = econ.metrics()
            runs[policy] = {
                "series": _series(econ, SHOCK_STEP if shocks else 0),
                "drift_pct": round(m["price_drift_pct"], 2),
                "max_dev_pct": round(m["price_max_dev_pct"], 2),
                "money_change_pct": round(m["money_supply_change_pct"], 2),
                "recovery_steps": m["recovery_steps"],
                "minted": round(m["total_minted"], 1),
                "burned": round(m["total_burned"], 1),
            }
        out.append({"key": key, "label": label, "shock_step": SHOCK_STEP if shocks else None, "runs": runs})
    return out


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
        for policy, params in (("null", {}), ("trend", {}), ("anchored", {"gain": 0.1}), ("anchored", {"gain": 0.5})):
            name = policy if policy != "anchored" else f"anchored_g{params['gain']}"
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


def bias_panel() -> dict:
    """Steady-state drift with no shock at all: the controller acting on noise alone."""
    base = base_config()
    variants = {
        "trend_asymmetric": ("trend", {}),
        "trend_symmetric": ("trend", {"asymmetric": False}),
        "anchored": ("anchored", {}),
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
            "policies": POLICY_LABELS,
        },
        "shocks": shocks_panel(),
        "granularity_sweep": granularity_sweep(),
        "gain_sweep": gain_sweep(),
        "bias": bias_panel(),
    }
