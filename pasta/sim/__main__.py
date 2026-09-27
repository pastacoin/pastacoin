"""Command line for PastaTester.

Examples::

    python -m pasta.sim --controller null --shock 2000:money_demand:1.5
    python -m pasta.sim --controller trend --shock 2000:money_demand:1.5 --csv out.csv
    python -m pasta.sim --compare --shock 2000:volume:2.0
"""
from __future__ import annotations

import argparse
import json

from pasta.sim.economy import Shock, SimConfig, run_simulation

CONTROLLERS = ["null", "fixed", "trend"]


def _fmt(m: dict) -> str:
    return (f"{m['controller']:<6} drift {m['price_drift_pct']:+7.2f}%  maxdev {m['price_max_dev_pct']:6.2f}%  "
            f"stdev {m['price_stdev_pct']:5.2f}%  M {m['money_supply_change_pct']:+7.2f}%  "
            f"minted {m['total_minted']:9.1f} burned {m['total_burned']:9.1f} skipped {m['skipped_purchases']}  "
            f"recover {m['recovery_steps'] if m['recovery_steps'] is not None else '-'}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PaSta stability simulator")
    ap.add_argument("--controller", default="null", choices=CONTROLLERS)
    ap.add_argument("--agents", type=int, default=200)
    ap.add_argument("--steps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--money-demand", type=float, default=20.0)
    ap.add_argument("--buy-probability", type=float, default=0.10)
    ap.add_argument("--shock", action="append", default=[], metavar="STEP:KIND:FACTOR",
                    help="kind in money_demand | volume | agents | granularity | real_prices; repeatable")
    ap.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                    help="controller parameter, e.g. gain=0.3 (repeatable)")
    ap.add_argument("--csv", help="write per-step records to this CSV")
    ap.add_argument("--json", action="store_true", help="print metrics as JSON")
    ap.add_argument("--compare", action="store_true", help="run every controller with the same config")
    args = ap.parse_args(argv)

    kwargs = {}
    for kv in args.param:
        k, v = kv.split("=", 1)
        kwargs[k] = float(v) if v.replace(".", "", 1).replace("-", "", 1).isdigit() else v

    def cfg(controller: str) -> SimConfig:
        return SimConfig(
            agents=args.agents, steps=args.steps, seed=args.seed, controller=controller,
            controller_kwargs=kwargs if controller != "null" else {},
            money_demand=args.money_demand, buy_probability=args.buy_probability,
            shocks=[Shock.parse(s) for s in args.shock],
        )

    names = CONTROLLERS if args.compare else [args.controller]
    results = []
    for name in names:
        econ = run_simulation(cfg(name))
        m = econ.metrics()
        results.append(m)
        if args.csv and not args.compare:
            econ.write_csv(args.csv)
        elif args.csv:
            econ.write_csv(args.csv.replace(".csv", f"-{name}.csv"))
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for m in results:
            print(_fmt(m))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
