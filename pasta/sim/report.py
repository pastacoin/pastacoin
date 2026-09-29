"""Produce the simulation report artefacts: JSON for the website, PNG figures for the memo.

    python -m pasta.sim.report --json out/results.json --figures docs/figures

Figures need matplotlib (``pip install matplotlib``); the JSON does not.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import date

from pasta.sim.experiments import POLICY_LABELS, run_all

# Palette: validated categorical slots (see dataviz reference palette). The anchored rule is
# the story (slot 1 blue), the whitepaper trend rule is slot 2 orange, the baseline is gray.
COLORS = {"anchored": "#2a78d6", "trend": "#eb6834", "null": "#898781"}
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def _git_rev() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _style(ax, title: str, ylabel: str = "", xlabel: str = ""):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
        ax.spines[side].set_linewidth(1)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.set_title(title, loc="left", fontsize=10, color=INK, pad=8)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2, fontsize=8)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2, fontsize=8)


def make_figures(results: dict, out_dir: str) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
    os.makedirs(out_dir, exist_ok=True)
    written = []

    # 1. Small multiples: price level under each shock, three policies
    shocks = results["shocks"]
    fig, axes = plt.subplots(2, 4, figsize=(14, 6.4), facecolor=SURFACE)
    axes = axes.flatten()
    for ax, panel in zip(axes, shocks):
        for policy in ("null", "trend", "anchored"):
            s = panel["runs"][policy]["series"]
            ax.plot(s["step"], s["price_rel"], color=COLORS[policy], linewidth=2, solid_capstyle="round",
                    label=POLICY_LABELS[policy])
        if panel["shock_step"]:
            ax.axvline(panel["shock_step"], color="#c3c2b7", linewidth=1)
        ax.axhline(1.0, color="#c3c2b7", linewidth=1)
        _style(ax, panel["label"], ylabel="price level (pre-shock = 1)")
        ax.set_ylim(0.3, 2.2)
    axes[-1].axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    axes[-1].legend(handles, labels, loc="center", frameon=False, fontsize=9, labelcolor=INK2)
    fig.suptitle("PASTA price level after a shock at step 2000, by controller", x=0.01, ha="left",
                 fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p = os.path.join(out_dir, "shocks-small-multiples.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 2. Final drift per shock, grouped bars
    fig, ax = plt.subplots(figsize=(11, 4.6), facecolor=SURFACE)
    labels = [s["label"].split(":")[0] for s in shocks]
    x = range(len(shocks))
    width = 0.26
    for i, policy in enumerate(("null", "trend", "anchored")):
        vals = [s["runs"][policy]["drift_pct"] for s in shocks]
        bars = ax.bar([xi + (i - 1) * width for xi in x], vals, width=width * 0.9, color=COLORS[policy],
                      label=POLICY_LABELS[policy])
        for b, v in zip(bars, vals):
            if abs(v) >= 25:
                ax.annotate(f"{v:+.0f}%", (b.get_x() + b.get_width() / 2, v),
                            ha="center", va="bottom" if v >= 0 else "top", fontsize=7, color=INK2,
                            xytext=(0, 2 if v >= 0 else -2), textcoords="offset points")
    ax.axhline(0, color="#c3c2b7", linewidth=1)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8, color=INK2)
    _style(ax, "Change in price level from step 500 to 5000 (0 = purchasing power held)", ylabel="%")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="lower left")
    fig.tight_layout()
    p = os.path.join(out_dir, "drift-by-shock.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 3. Granularity sweep
    sweep = results["granularity_sweep"]["rows"]
    fig, ax = plt.subplots(figsize=(7, 4.4), facecolor=SURFACE)
    xs = [r["factor"] for r in sweep]
    series = [("null", "null", COLORS["null"], "-"), ("trend", "trend", COLORS["trend"], "-"),
              ("anchored_g0.1", "anchored, gain 0.1", COLORS["anchored"], "-"),
              ("anchored_g0.5", "anchored, gain 0.5", "#104281", "-")]
    for key, label, color, ls in series:
        ys = [r[key]["drift_pct"] for r in sweep]
        ax.plot(xs, ys, color=color, linewidth=2, linestyle=ls, marker="o", markersize=5, label=label)
    ax.axhline(0, color="#c3c2b7", linewidth=1)
    _style(ax, "Self-inflicted price change when transactions get larger (purchasing power unchanged)",
           ylabel="price level change, %", xlabel="transaction size factor (same total spending)")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    p = os.path.join(out_dir, "granularity-sweep.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 4. Gain trade-off: two charts, one axis each
    gains = results["gain_sweep"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), facecolor=SURFACE)
    gx = [str(g["gain"]) for g in gains]
    rec = [g["recovery_steps"] if g["recovery_steps"] is not None else 0 for g in gains]
    bars = a1.bar(gx, rec, width=0.5, color=COLORS["anchored"])
    for b, g in zip(bars, gains):
        if g["recovery_steps"] is None:
            a1.annotate("no recovery\nwithin run", (b.get_x() + b.get_width() / 2, 40), ha="center", fontsize=7, color=INK2)
    _style(a1, "Steps to get back within 5% after hoarding shock", ylabel="steps", xlabel="gain")
    a2.bar(gx, [g["minted"] for g in gains], width=0.5, color="#86b6ef", label="minted")
    a2.bar(gx, [g["burned"] for g in gains], width=0.5, bottom=[g["minted"] for g in gains],
           color="#104281", label="burned")
    _style(a2, "Total mint + burn churn over the run", ylabel="PASTA", xlabel="gain")
    a2.legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    p = os.path.join(out_dir, "gain-tradeoff.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 6. Round two: shocks and attacks, four policies (gray baseline + three validated slots)
    V2 = {"null": COLORS["null"], "anchored": COLORS["anchored"], "size": "#1baf7a", "flow": COLORS["trend"]}
    V2_LABEL = {"null": "No controller", "anchored": "Round one: anchored average", "size": "Median size, supply-sized, capped",
                "flow": "Flow per holder, supply-sized, capped"}
    panels = results["shocks_v2"] + results["attacks"]
    fig, axes = plt.subplots(3, 3, figsize=(14, 9.6), facecolor=SURFACE)
    axes = axes.flatten()
    for ax, panel in zip(axes, panels):
        for policy in ("null", "anchored", "size", "flow"):
            s = panel["runs"][policy]["series"]
            ax.plot(s["step"], s["price_rel"], color=V2[policy], linewidth=2, solid_capstyle="round", label=V2_LABEL[policy])
        if panel["shock_step"]:
            ax.axvline(panel["shock_step"], color="#c3c2b7", linewidth=1)
        ax.axhline(1.0, color="#c3c2b7", linewidth=1)
        _style(ax, panel["label"], ylabel="price level (pre-shock = 1)")
        ax.set_ylim(0.3, 2.2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=9, labelcolor=INK2)
    fig.suptitle("Round two: supply-sized, rate-capped controllers under the same shocks plus two attacks (money demand 100)",
                 x=0.01, ha="left", fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    p = os.path.join(out_dir, "round2-shocks-attacks.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 7. What the cap buys: recovery time vs damage from a saturated misread
    caps = results["cap_sweep"]
    labels = ["none" if c["cap_rate"] is None else f"{c['cap_rate'] * 100:.2f}%" for c in caps]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4), facecolor=SURFACE)
    rec = [c["hoarding_recovery"] if c["hoarding_recovery"] is not None else 0 for c in caps]
    a1.bar(labels, rec, width=0.5, color="#1baf7a")
    _style(a1, "Steps to recover from hoarding (median-size rule, gain 0.01)", ylabel="steps", xlabel="cap: max supply change per period")
    a2.bar(labels, [max(c["misread_drift_pct"], 1) for c in caps], width=0.5, color=COLORS["trend"])
    a2.set_yscale("log")
    _style(a2, "Damage when the signal is fooled (sybil dust, no dust floor)", ylabel="price level change, % (log)", xlabel="cap: max supply change per period")
    fig.tight_layout()
    p = os.path.join(out_dir, "round2-cap-tradeoff.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 8. Growth allowance: steady real growth
    ga = results["growth_allowance_sweep"]
    fig, ax = plt.subplots(figsize=(7.5, 4.4), facecolor=SURFACE)
    xs = [f"{g['growth_per_period'] * 100:.2f}%" for g in ga]
    ax.plot(xs, [g["flow_growth_drift_pct"] for g in ga], color=COLORS["trend"], linewidth=2, marker="o", markersize=5, label="flow rule, steady growth")
    ax.plot(xs, [g["flow_no_growth_drift_pct"] for g in ga], color="#d95926", linewidth=2, marker="o", markersize=5, linestyle=(0, (4, 3)), label="flow rule, no growth")
    ax.axhline(ga[0]["size_growth_drift_pct"], color="#1baf7a", linewidth=2, label="median-size rule, steady growth (no allowance needed)")
    ax.axhline(ga[0]["null_growth_drift_pct"], color=COLORS["null"], linewidth=2, label="no controller, steady growth")
    ax.axhline(0, color="#c3c2b7", linewidth=1)
    _style(ax, f"Growth allowance vs true growth of {results['config']['growth_rate'] * 100:.2f}% per period",
           ylabel="price level change, %", xlabel="allowance: anchor growth per period")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    p = os.path.join(out_dir, "round2-growth-allowance.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)

    # 5. Bias with no shock
    bias = results["bias"]
    fig, ax = plt.subplots(figsize=(7, 4.2), facecolor=SURFACE)
    for key, label, color in (("trend_asymmetric", "trend, asymmetric (whitepaper)", COLORS["trend"]),
                              ("trend_symmetric", "trend, symmetric", "#1baf7a"),
                              ("anchored", "anchored, gain 0.1", COLORS["anchored"])):
        s = bias[key]["series"]
        ax.plot(s["step"], s["price_rel"], color=color, linewidth=2, label=label)
    ax.axhline(1.0, color="#c3c2b7", linewidth=1)
    _style(ax, "No shock: what the controller does on noise alone", ylabel="price level (start = 1)", xlabel="step")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    p = os.path.join(out_dir, "bias-no-shock.png")
    fig.savefig(p, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    written.append(p)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build simulation report artefacts")
    ap.add_argument("--json", help="write results JSON here")
    ap.add_argument("--js", help="write results as a JS file assigning window.PASTA_RESULTS")
    ap.add_argument("--figures", help="write PNG figures into this directory")
    args = ap.parse_args(argv)

    results = run_all()
    results["meta"] = {"generated": date.today().isoformat(), "commit": _git_rev()}
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, separators=(",", ":"))
        print("wrote", args.json)
    if args.js:
        os.makedirs(os.path.dirname(os.path.abspath(args.js)), exist_ok=True)
        with open(args.js, "w", encoding="utf-8") as fh:
            fh.write("window.PASTA_RESULTS = ")
            json.dump(results, fh, separators=(",", ":"))
            fh.write(";\n")
        print("wrote", args.js)
    if args.figures:
        for p in make_figures(results, args.figures):
            print("wrote", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
