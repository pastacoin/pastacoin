"""Bitcoin as a fixed-supply economy: does transaction size shrink as the economy grows?

Recreates the whitepaper's Bitcoin chart from public data and corrects it:

* uses *estimated* transaction value (change outputs removed) rather than raw output value;
* adjusts for newly minted coins by expressing transaction size as a share of circulating
  supply, so supply growth (≈2x since 2011) cannot masquerade as shrinking transactions;
* reports the USD value of the average transaction alongside the BTC value, which is the
  quantity the PaSta thesis actually cares about (is the *real* size of a transaction stable?);
* shows fee pressure, the sign of block-space saturation that pushes small payments off chain.

Data: blockchain.com charts API (no key). ``fetch()`` downloads the daily series and writes a
slim CSV (``data/bitcoin-daily.csv``) that is committed so the analysis is reproducible offline.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import statistics
import urllib.request
from collections import defaultdict
from typing import Dict, List, Optional

SERIES = {
    "price_usd": "market-price",
    "tx_count": "n-transactions",
    "est_volume_btc": "estimated-transaction-volume",
    "est_volume_usd": "estimated-transaction-volume-usd",
    "supply_btc": "total-bitcoins",
    "active_addresses": "n-unique-addresses",
    "fees_usd": "transaction-fees-usd",
    "output_volume_btc": "output-volume",
}
API = "https://api.blockchain.info/charts/{chart}?timespan=all&format=json&sampled=false"
DEFAULT_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "bitcoin-daily.csv")


# ------------------------------------------------------------------ data ----

def _download(chart: str) -> Dict[dt.date, float]:
    with urllib.request.urlopen(API.format(chart=chart), timeout=120) as resp:
        data = json.load(resp)
    out: Dict[dt.date, float] = {}
    for p in data.get("values", []):
        d = dt.datetime.fromtimestamp(p["x"], dt.timezone.utc).date()
        out[d] = float(p["y"])  # for sub-daily series (supply) the last sample of the day wins
    return out


def fetch(csv_path: str = DEFAULT_CSV) -> str:
    """Download every series and write the slim daily CSV. Returns the path."""
    cols = {k: _download(chart) for k, chart in SERIES.items()}
    days = sorted(set().union(*[set(c) for c in cols.values()]))
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", *SERIES.keys()])
        for d in days:
            w.writerow([d.isoformat(), *["" if d not in cols[k] else f"{cols[k][d]:.10g}" for k in SERIES]])
    return csv_path


def load(csv_path: str = DEFAULT_CSV) -> List[dict]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            row = {"date": dt.date.fromisoformat(r["date"])}
            for k in SERIES:
                row[k] = float(r[k]) if r[k] not in ("", None) else None
            rows.append(row)
    return rows


# --------------------------------------------------------------- metrics ----

def daily_metrics(rows: List[dict]) -> List[dict]:
    """Per-day derived quantities; None where inputs are missing or zero."""
    out = []
    for r in rows:
        n, vb, vu, s, p = r["tx_count"], r["est_volume_btc"], r["est_volume_usd"], r["supply_btc"], r["price_usd"]
        m = dict(r)
        m["mean_tx_btc"] = vb / n if n and vb else None
        m["mean_tx_usd"] = vu / n if n and vu else None
        m["mean_tx_share_ppm"] = (vb / n) / s * 1e6 if n and vb and s else None   # millionths of supply
        m["market_cap_usd"] = p * s if p and s else None
        m["fee_per_tx_usd"] = r["fees_usd"] / n if n and r["fees_usd"] is not None else None
        out.append(m)
    return out


def monthly(rows: List[dict], keys: List[str], start_year: int = 2011) -> List[dict]:
    """Monthly medians of daily values (robust to single-day spikes)."""
    buckets: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["date"].year < start_year:
            continue
        key = r["date"].strftime("%Y-%m")
        for k in keys:
            if r.get(k) is not None:
                buckets[key][k].append(r[k])
    out = []
    for key in sorted(buckets):
        rec = {"month": key}
        for k in keys:
            vals = buckets[key][k]
            rec[k] = statistics.median(vals) if vals else None
        out.append(rec)
    return out


def yearly(rows: List[dict], keys: List[str], start_year: int = 2011) -> List[dict]:
    buckets: Dict[int, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["date"].year < start_year:
            continue
        for k in keys:
            if r.get(k) is not None:
                buckets[r["date"].year][k].append(r[k])
    out = []
    for y in sorted(buckets):
        rec = {"year": y}
        for k in keys:
            vals = buckets[y][k]
            rec[k] = statistics.median(vals) if vals else None
        out.append(rec)
    return out


def log_slope(xs: List[float], ys: List[float]) -> Optional[dict]:
    """OLS slope of log(y) on log(x): the elasticity. Returns slope, intercept, r2, n."""
    pts = [(math.log(x), math.log(y)) for x, y in zip(xs, ys) if x and y and x > 0 and y > 0]
    n = len(pts)
    if n < 3:
        return None
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    slope = sxy / sxx if sxx else float("nan")
    intercept = my - slope * mx
    ss_tot = sum((p[1] - my) ** 2 for p in pts)
    ss_res = sum((p[1] - (intercept + slope * p[0])) ** 2 for p in pts)
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
    return {"slope": slope, "intercept": intercept, "r2": r2, "n": n}


def fixed_supply_toy(users: List[float], supply: float = 1.0, k: float = 1.0) -> Dict[str, List[float]]:
    """The coarse demonstration.

    A fixed-supply coin in an economy of ``users`` people who each want to hold ``k`` units of
    real spending as money and who each make the same real purchases. Quantity theory then gives
    price per coin ∝ users and coins per transaction ∝ 1 / users. Returned relative to the
    first period.
    """
    n0 = users[0]
    return {
        "users_rel": [u / n0 for u in users],
        "price_rel": [u / n0 for u in users],
        "coins_per_tx_rel": [n0 / u for u in users],
    }


# --------------------------------------------------------------- summary ----

def summary(rows: Optional[List[dict]] = None, csv_path: str = DEFAULT_CSV) -> dict:
    rows = daily_metrics(rows or load(csv_path))
    keys = ["price_usd", "market_cap_usd", "supply_btc", "tx_count", "active_addresses",
            "mean_tx_btc", "mean_tx_usd", "mean_tx_share_ppm", "fee_per_tx_usd"]
    mon = monthly(rows, keys)
    yr = yearly(rows, keys)
    good = [m for m in mon if all(m.get(k) for k in ("price_usd", "mean_tx_btc", "mean_tx_usd", "mean_tx_share_ppm", "market_cap_usd", "active_addresses"))]
    elasticity = {
        "tx_btc_vs_price": log_slope([m["price_usd"] for m in good], [m["mean_tx_btc"] for m in good]),
        "tx_share_vs_market_cap": log_slope([m["market_cap_usd"] for m in good], [m["mean_tx_share_ppm"] for m in good]),
        "tx_share_vs_active_addresses": log_slope([m["active_addresses"] for m in good], [m["mean_tx_share_ppm"] for m in good]),
        "tx_usd_vs_price": log_slope([m["price_usd"] for m in good], [m["mean_tx_usd"] for m in good]),
    }
    first, last = yr[0], yr[-1]
    return {
        "range": {"first_month": mon[0]["month"], "last_month": mon[-1]["month"], "last_day": rows[-1]["date"].isoformat()},
        "yearly": yr,
        "monthly": mon,
        "elasticity": elasticity,
        "ratios_first_to_last_year": {
            k: (last[k] / first[k] if first.get(k) and last.get(k) else None) for k in keys
        },
        "toy": fixed_supply_toy([1, 2, 5, 10, 20, 50, 100]),
    }
