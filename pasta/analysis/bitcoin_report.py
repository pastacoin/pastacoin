"""Figures and website data for the Bitcoin fixed-supply demonstration.

    python -m pasta.analysis.bitcoin_report --figures docs/figures --js ../pastacoin.github.io/results/bitcoin-data.js
    python -m pasta.analysis.bitcoin_report --fetch      # refresh data/bitcoin-daily.csv first
"""
from __future__ import annotations

import argparse
import json
import math
import os
from datetime import date

from pasta.analysis import bitcoin as b
from pasta.sim.report import COLORS, GRID, INK, INK2, MUTED, SURFACE, _git_rev, _style

BLUE, BLUE_DARK, ORANGE, GRAY = "#2a78d6", "#104281", "#eb6834", "#898781"


def build_data() -> dict:
    rows = b.daily_metrics(b.load())
    s = b.summary(rows)
    keys = ["price_usd", "market_cap_usd", "active_addresses", "mean_tx_btc", "mean_tx_usd",
            "mean_tx_share_ppm", "fee_per_tx_usd", "tx_count", "supply_btc"]
    mon = [m for m in s["monthly"] if all(m.get(k) for k in keys)]

    def era(lo: str, hi: str) -> dict:
        g = [m for m in mon if lo <= m["month"][:4] <= hi]
        out = {"from": lo, "to": hi, "months": len(g)}
        for name, x, y in (("tx_btc_vs_price", "price_usd", "mean_tx_btc"),
                           ("tx_usd_vs_price", "price_usd", "mean_tx_usd"),
                           ("share_vs_users", "active_addresses", "mean_tx_share_ppm"),
                           ("share_vs_market_cap", "market_cap_usd", "mean_tx_share_ppm")):
            e = b.log_slope([m[x] for m in g], [m[y] for m in g])
            out[name] = {"slope": round(e["slope"], 3), "r2": round(e["r2"], 3)} if e else None
        fees = sorted(m["fee_per_tx_usd"] for m in g)
        out["median_fee_per_tx_usd"] = round(fees[len(fees) // 2], 3) if fees else None
        return out

    first, last = s["yearly"][0], s["yearly"][-1]
    return {
        "meta": {"generated": date.today().isoformat(), "commit": _git_rev(), "data_last_day": s["range"]["last_day"],
                 "source": "blockchain.com charts API: market-price, n-transactions, estimated-transaction-volume(-usd), total-bitcoins, n-unique-addresses, transaction-fees-usd"},
        "monthly": [{k: (round(m[k], 6) if isinstance(m[k], float) else m[k]) for k in ["month", *keys]} for m in mon],
        "yearly": [{k: (round(y[k], 6) if isinstance(y.get(k), float) else y.get(k)) for k in ["year", *keys]} for y in s["yearly"]],
        "eras": [era("2011", "2016"), era("2017", "2026"), era("2011", "2026")],
        "ratios": {k: (round(v, 3) if v else None) for k, v in s["ratios_first_to_last_year"].items()},
        "first_year": first["year"], "last_year": last["year"],
        "toy": s["toy"],
    }


def make_figures(data: dict, out_dir: str) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
    os.makedirs(out_dir, exist_ok=True)
    mon = data["monthly"]
    x = [date(int(m["month"][:4]), int(m["month"][5:]), 1) for m in mon]
    written = []

    # 1. Price and coins per transaction: two panels, one axis each, log scale
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 9), sharex=True, facecolor=SURFACE)
    a1.plot(x, [m["price_usd"] for m in mon], color=GRAY, linewidth=2)
    a1.set_yscale("log")
    _style(a1, "Bitcoin price, USD (monthly median)")
    a2.plot(x, [m["mean_tx_btc"] for m in mon], color=ORANGE, linewidth=2, label="BTC per transaction (raw)")
    a2.set_yscale("log")
    _style(a2, "Average transaction size in BTC: estimated volume / transactions")
    a3.plot(x, [m["mean_tx_share_ppm"] for m in mon], color=BLUE, linewidth=2)
    a3.set_yscale("log")
    _style(a3, "Same, adjusted for minted coins: millionths of circulating supply per transaction", xlabel="")
    a3.xaxis.set_major_locator(mdates.YearLocator(2))
    a3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle("As Bitcoin's economy grew, each transaction became a smaller slice of a fixed supply",
                 x=0.01, ha="left", fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    p = os.path.join(out_dir, "bitcoin-price-vs-txsize.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 2. Real size of a transaction and fee pressure
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, facecolor=SURFACE)
    a1.plot(x, [m["mean_tx_usd"] for m in mon], color=ORANGE, linewidth=2)
    a1.set_yscale("log")
    _style(a1, "Average transaction size in USD (what the transaction was actually worth)")
    a2.plot(x, [max(m["fee_per_tx_usd"], 1e-3) for m in mon], color=GRAY, linewidth=2)
    a2.set_yscale("log")
    _style(a2, "Fee per transaction, USD: the price of block space")
    a2.xaxis.set_major_locator(mdates.YearLocator(2))
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle("The whitepaper's confound: on-chain transactions got much larger in real terms as fees rose",
                 x=0.01, ha="left", fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p = os.path.join(out_dir, "bitcoin-usd-size-and-fees.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 3. The demonstration: share of supply per transaction vs users, log-log, with the toy 1/N line
    fig, ax = plt.subplots(figsize=(8, 6), facecolor=SURFACE)
    xs = [m["active_addresses"] for m in mon]
    ys = [m["mean_tx_share_ppm"] for m in mon]
    early = [i for i, m in enumerate(mon) if m["month"] < "2017"]
    late = [i for i, m in enumerate(mon) if m["month"] >= "2017"]
    ax.scatter([xs[i] for i in early], [ys[i] for i in early], s=18, color=BLUE, edgecolors=SURFACE, linewidths=1.5, label="2011-2016 (fees near zero)")
    ax.scatter([xs[i] for i in late], [ys[i] for i in late], s=18, color=ORANGE, edgecolors=SURFACE, linewidths=1.5, label="2017-2026 (block space scarce)")
    e = next(er for er in data["eras"] if er["from"] == "2011" and er["to"] == "2026")["share_vs_users"]
    lo, hi = min(xs), max(xs)
    # anchor the toy's slope -1 line at the log-centroid of the free-block-space era
    cx = math.exp(sum(math.log(xs[i]) for i in early) / len(early))
    cy = math.exp(sum(math.log(ys[i]) for i in early) / len(early))
    ax.plot([lo, hi], [cy * cx / lo, cy * cx / hi], color=GRAY, linewidth=2, label="fixed-supply toy: coins per tx ∝ 1 / users")
    fit = b.log_slope(xs, ys)
    ax.plot([lo, hi], [math.exp(fit["intercept"]) * lo ** fit["slope"], math.exp(fit["intercept"]) * hi ** fit["slope"]],
            color=BLUE_DARK, linewidth=2, linestyle=(0, (4, 3)), label=f"fit to data: slope {fit['slope']:+.2f}, r² {fit['r2']:.2f}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    _style(ax, "Slice of supply per transaction vs. number of active addresses (monthly medians)",
           ylabel="millionths of supply per transaction", xlabel="active addresses per day")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="lower left")
    fig.tight_layout()
    p = os.path.join(out_dir, "bitcoin-share-vs-users.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 4. The toy itself
    toy = data["toy"]
    fig, ax = plt.subplots(figsize=(7, 4.4), facecolor=SURFACE)
    ax.plot(toy["users_rel"], toy["price_rel"], color=GRAY, linewidth=2, marker="o", markersize=5, label="price per coin")
    ax.plot(toy["users_rel"], toy["coins_per_tx_rel"], color=BLUE, linewidth=2, marker="o", markersize=5, label="coins per transaction")
    ax.set_xscale("log")
    ax.set_yscale("log")
    _style(ax, "Fixed supply, growing economy: the coarse model", ylabel="relative to start", xlabel="users, relative to start")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    p = os.path.join(out_dir, "bitcoin-toy.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bitcoin fixed-supply demonstration artefacts")
    ap.add_argument("--fetch", action="store_true", help="refresh data/bitcoin-daily.csv from blockchain.com")
    ap.add_argument("--json")
    ap.add_argument("--js", help="write window.PASTA_BITCOIN = ... for the website")
    ap.add_argument("--figures")
    args = ap.parse_args(argv)
    if args.fetch:
        print("wrote", b.fetch())
    data = build_data()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"))
        print("wrote", args.json)
    if args.js:
        os.makedirs(os.path.dirname(os.path.abspath(args.js)), exist_ok=True)
        with open(args.js, "w", encoding="utf-8") as fh:
            fh.write("window.PASTA_BITCOIN = ")
            json.dump(data, fh, separators=(",", ":"))
            fh.write(";\n")
        print("wrote", args.js)
    if args.figures:
        for p in make_figures(data, args.figures):
            print("wrote", p)
    if not (args.json or args.js or args.figures):
        for er in data["eras"]:
            print(er)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
