"""Figures and website data for the multi-chain fixed-supply demonstration.

    python -m pasta.analysis.chains_report --figures docs/figures --js ../pastacoin.github.io/results/chains-data.js
    python -m pasta.analysis.chains_report --fetch ltc eth     # refresh data/chains/<chain>-daily.csv first

Chains are included when their CSV exists. A chain whose daily median transfer value is zero
for most months (unfiltered Ethereum, dust-dominated periods) is flagged ``median_ok = false``
and left out of the median-based charts.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import date

from pasta.analysis import chains as ch
from pasta.sim.report import GRID, INK, INK2, MUTED, SURFACE, _git_rev, _style

# Categorical slots (validated adjacent order): blue, orange, aqua, yellow, magenta
CHAIN_COLORS = {"btc": "#2a78d6", "eth": "#eb6834", "ltc": "#1baf7a", "doge": "#eda100", "bch": "#e87ba4"}
GRAY = "#898781"


def build_data() -> dict:
    chains = []
    for key in ch.CHAINS:
        if not os.path.exists(ch.csv_path(key)):
            continue
        s = ch.summary(key)
        mon = s["monthly"]
        nonzero = sum(1 for m in mon if m.get("median_tx_native"))
        s["median_months"] = nonzero
        s["median_ok"] = s["median_usable"] and nonzero >= 24 and bool(s["eras"][0].get("median_native_vs_price"))
        s["color"] = CHAIN_COLORS.get(key, GRAY)
        chains.append(s)
    return {
        "meta": {"generated": date.today().isoformat(), "commit": _git_rev(),
                 "sources": "Blockchair daily transaction aggregates (count, sum, median, mean of transfer value); CoinMetrics community data (price, supply, transaction count, active addresses, fees)"},
        "chains": chains,
    }


def _months_to_dates(mon):
    return [date(int(m["month"][:4]), int(m["month"][5:]), 1) for m in mon]


def make_figures(data: dict, out_dir: str) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
    os.makedirs(out_dir, exist_ok=True)
    written = []
    chains = [c for c in data["chains"] if c["median_ok"]]
    if not chains:
        return written

    # 1. Per chain: price and median transaction size in coin units, both indexed to the first
    #    year (one axis). If the median tracks purchasing power the two lines mirror each other.
    n = len(chains)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 4.4), facecolor=SURFACE, squeeze=False)
    for ax, c in zip(axes[0], chains):
        mon = [m for m in c["monthly"] if m.get("price_usd") and m.get("median_tx_native")]
        x = _months_to_dates(mon)
        p0, t0 = mon[0]["price_usd"], mon[0]["median_tx_native"]
        ax.plot(x, [m["price_usd"] / p0 for m in mon], color=GRAY, linewidth=2, label="price (indexed)")
        ax.plot(x, [m["median_tx_native"] / t0 for m in mon], color=c["color"], linewidth=2, label="median transaction, coin units (indexed)")
        ax.set_yscale("log")
        e = c["eras"][0]["median_native_vs_price"]
        _style(ax, f"{c['name']}: elasticity {e['slope']:+.2f}", ylabel="index (first month = 1)")
        ax.xaxis.set_major_locator(mdates.YearLocator(3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.legend(frameon=False, fontsize=7, labelcolor=INK2, loc="upper left")
    fig.suptitle("Price up, coins per median transaction down: elasticity near -1 means the median tracks purchasing power",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = os.path.join(out_dir, "chains-price-vs-median.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 2. Median transaction size in USD over time, all chains on one log axis
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=SURFACE)
    for c in chains:
        mon = [m for m in c["monthly"] if m.get("median_tx_usd")]
        ax.plot(_months_to_dates(mon), [m["median_tx_usd"] for m in mon], color=c["color"], linewidth=2, label=c["name"])
    ax.set_yscale("log")
    _style(ax, "What the median transaction was worth, USD (monthly medians)", ylabel="USD")
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    p = os.path.join(out_dir, "chains-median-usd.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 3. Elasticity summary: two panels, one axis each
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4), facecolor=SURFACE)
    names = [c["name"] for c in chains]
    e_native = [c["eras"][0]["median_native_vs_price"]["slope"] for c in chains]
    e_usd = [c["eras"][0]["median_usd_vs_price"]["slope"] for c in chains]
    cols = [c["color"] for c in chains]
    a1.bar(names, e_native, width=0.5, color=cols)
    a1.axhline(-1, color="#c3c2b7", linewidth=1)
    a1.axhline(0, color="#c3c2b7", linewidth=1)
    a1.text(len(names) - 0.5, -1, " -1 = tracks purchasing power exactly", fontsize=7, color=INK2, va="bottom", ha="right")
    _style(a1, "Median coins per transaction vs price (elasticity)")
    a2.bar(names, e_usd, width=0.5, color=cols)
    a2.axhline(0, color="#c3c2b7", linewidth=1)
    a2.axhline(1, color="#c3c2b7", linewidth=1)
    a2.text(len(names) - 0.5, 0, " 0 = real size unchanged", fontsize=7, color=INK2, va="bottom", ha="right")
    _style(a2, "Median USD per transaction vs price (elasticity)")
    for a in (a1, a2):
        a.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    p = os.path.join(out_dir, "chains-elasticities.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 4. Share of supply per median transaction vs active addresses, log-log, per chain
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n, 4.4), facecolor=SURFACE, squeeze=False)
    for ax, c in zip(axes[0], chains):
        mon = [m for m in c["monthly"] if m.get("active_addresses") and m.get("median_tx_share_ppm")]
        xs = [m["active_addresses"] for m in mon]
        ys = [m["median_tx_share_ppm"] for m in mon]
        ax.scatter(xs, ys, s=14, color=c["color"], edgecolors=SURFACE, linewidths=1.2)
        e = c["eras"][0]["median_share_vs_users"]
        if e and xs:
            lo, hi = min(xs), max(xs)
            cx = math.exp(sum(math.log(v) for v in xs) / len(xs))
            cy = math.exp(sum(math.log(v) for v in ys) / len(ys))
            ax.plot([lo, hi], [cy * (lo / cx) ** e["slope"], cy * (hi / cx) ** e["slope"]], color=INK2, linewidth=1.5,
                    linestyle=(0, (4, 3)), label=f"fit slope {e['slope']:+.2f}, r² {e['r2']:.2f}")
            ax.plot([lo, hi], [cy * cx / lo, cy * cx / hi], color=GRAY, linewidth=1.5, label="toy: slope -1")
        ax.set_xscale("log")
        ax.set_yscale("log")
        _style(ax, c["name"], ylabel="millionths of supply, median tx", xlabel="active addresses / day")
        ax.legend(frameon=False, fontsize=7, labelcolor=INK2, loc="lower left")
    fig.suptitle("Slice of supply per median transaction vs users (monthly medians)", x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = os.path.join(out_dir, "chains-share-vs-users.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Multi-chain fixed-supply demonstration artefacts")
    ap.add_argument("--fetch", nargs="*", metavar="CHAIN", help="refresh these chains from Blockchair + CoinMetrics (60 s apart)")
    ap.add_argument("--json")
    ap.add_argument("--js", help="write window.PASTA_CHAINS = ... for the website")
    ap.add_argument("--figures")
    args = ap.parse_args(argv)
    if args.fetch is not None:
        for i, key in enumerate(args.fetch or list(ch.CHAINS)):
            if i:
                time.sleep(60)
            print("wrote", ch.fetch(key))
    data = build_data()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"))
        print("wrote", args.json)
    if args.js:
        os.makedirs(os.path.dirname(os.path.abspath(args.js)), exist_ok=True)
        with open(args.js, "w", encoding="utf-8") as fh:
            fh.write("window.PASTA_CHAINS = ")
            json.dump(data, fh, separators=(",", ":"))
            fh.write(";\n")
        print("wrote", args.js)
    if args.figures:
        for p in make_figures(data, args.figures):
            print("wrote", p)
    if not (args.json or args.js or args.figures):
        for c in data["chains"]:
            e = c["eras"][0]
            print(f"{c['name']:<13} median_ok={c['median_ok']} native~price {e['median_native_vs_price']} usd~price {e['median_usd_vs_price']} share~users {e['median_share_vs_users']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
