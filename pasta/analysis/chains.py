"""The fixed-supply demonstration across several public chains.

Same question as :mod:`pasta.analysis.bitcoin`, asked of every chain with free daily data:
as the economy grows, does each transaction become a smaller slice of the supply, and does
the average (or median) transaction track purchasing power?

Sources (no API keys):

* **Blockchair** aggregated daily transaction stats: count, sum, median and mean of
  transferred value. For UTXO chains the value is ``output_total`` (includes change outputs,
  so levels overstate true transfers; the median is far less affected). For Ethereum it is
  the ETH ``value`` of plain transfers with value >= 0.001 ETH, which removes contract calls
  with zero value but also ignores ERC-20 and stablecoin transfers.
* **CoinMetrics community data** (GitHub CSV): price, circulating supply, transaction count,
  active addresses, total fees in native units, market cap.

``fetch(chain)`` writes ``data/chains/<chain>-daily.csv``; those files are committed.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

from pasta.analysis.bitcoin import log_slope, monthly, yearly

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "chains")
BLOCKCHAIR = "https://api.blockchair.com/{slug}/transactions?a=date,count(),sum({field}),median({field}),avg({field})&limit=10000&s=date(asc){q}"
COINMETRICS = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/{symbol}.csv"


@dataclass(frozen=True)
class Chain:
    key: str
    name: str
    symbol: str            # CoinMetrics file / ticker
    slug: str              # Blockchair path
    field: str             # Blockchair value column
    unit: float            # native units per coin (1e8 satoshi, 1e18 wei)
    start_year: int
    query: str = ""        # extra Blockchair filter, e.g. "&q=value(0.001..)"
    saturation_year: Optional[int] = None   # first year block space was persistently scarce
    supply_note: str = ""


CHAINS: Dict[str, Chain] = {
    "btc": Chain("btc", "Bitcoin", "btc", "bitcoin", "output_total", 1e8, 2011, saturation_year=2017,
                 supply_note="capped at 21M; issuance halves every four years"),
    "eth": Chain("eth", "Ethereum", "eth", "ethereum", "value", 1e18, 2016, query="&q=value(0.001..)", saturation_year=2020,
                 supply_note="no cap; issuance cut by the 2022 merge, fees burned since 2021"),
    "ltc": Chain("ltc", "Litecoin", "ltc", "litecoin", "output_total", 1e8, 2012, saturation_year=None,
                 supply_note="capped at 84M; never capacity constrained"),
    "doge": Chain("doge", "Dogecoin", "doge", "dogecoin", "output_total", 1e8, 2014, saturation_year=None,
                 supply_note="uncapped; fixed 5B coins per year, so inflation falls over time"),
    "bch": Chain("bch", "Bitcoin Cash", "bch", "bitcoin-cash", "output_total", 1e8, 2018, saturation_year=None,
                 supply_note="Bitcoin fork (Aug 2017) with large blocks; shares Bitcoin history before the fork"),
}

CM_COLUMNS = {"PriceUSD": "price_usd", "SplyCur": "supply", "TxCnt": "tx_count", "AdrActCnt": "active_addresses",
              "FeeTotNtv": "fees_native", "CapMrktCurUSD": "market_cap_usd"}
OUT_COLUMNS = ["date", "price_usd", "supply", "tx_count", "active_addresses", "fees_native", "market_cap_usd",
               "bc_tx_count", "bc_sum_value", "bc_median_value", "bc_mean_value"]


def csv_path(chain: str) -> str:
    return os.path.join(DATA_DIR, f"{chain}-daily.csv")


# ------------------------------------------------------------------ fetch ----

def _get(url: str, timeout: int = 300) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pastacoin-analysis/0.2"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_blockchair(chain: Chain) -> Dict[dt.date, dict]:
    data = json.loads(_get(BLOCKCHAIR.format(slug=chain.slug, field=chain.field, q=chain.query)))
    rows = data.get("data") or []
    if not rows:
        raise RuntimeError(f"Blockchair returned no rows for {chain.slug}: {data.get('context', {}).get('error')}")
    out = {}
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        out[d] = {
            "bc_tx_count": float(r["count()"]),
            "bc_sum_value": float(r[f"sum({chain.field})"]) / chain.unit,
            "bc_median_value": float(r[f"median({chain.field})"]) / chain.unit,
            "bc_mean_value": float(r[f"avg({chain.field})"]) / chain.unit,
        }
    return out


def fetch_coinmetrics(chain: Chain) -> Dict[dt.date, dict]:
    text = _get(COINMETRICS.format(symbol=chain.symbol)).decode("utf-8")
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        d = dt.date.fromisoformat(r["time"][:10])
        rec = {}
        for src, dst in CM_COLUMNS.items():
            v = r.get(src, "")
            rec[dst] = float(v) if v not in ("", "NaN", None) else None
        out[d] = rec
    return out


def fetch(chain_key: str) -> str:
    chain = CHAINS[chain_key]
    bc = fetch_blockchair(chain)
    cm = fetch_coinmetrics(chain)
    days = sorted(set(bc) | set(cm))
    os.makedirs(DATA_DIR, exist_ok=True)
    path = csv_path(chain_key)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(OUT_COLUMNS)
        for d in days:
            rec = {**cm.get(d, {}), **bc.get(d, {})}
            w.writerow([d.isoformat(), *["" if rec.get(k) is None else f"{rec[k]:.10g}" for k in OUT_COLUMNS[1:]]])
    return path


# ------------------------------------------------------------------- load ----

def load(chain_key: str) -> List[dict]:
    rows = []
    with open(csv_path(chain_key), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            row = {"date": dt.date.fromisoformat(r["date"])}
            for k in OUT_COLUMNS[1:]:
                row[k] = float(r[k]) if r.get(k) not in ("", None) else None
            rows.append(row)
    return rows


DUST_USD = 0.05   # a daily median below this is spam/inscription dust, not a payment


def daily_metrics(rows: List[dict], dust_usd: float = DUST_USD) -> List[dict]:
    """Per-day derived quantities.

    Days whose median transfer is worth less than ``dust_usd`` are dust-dominated (inscription
    spam, tipping bots); their median-based metrics are set to None and ``dust_day`` is True so
    the share of such days can be reported. Mean-based metrics are kept.
    """
    out = []
    for r in rows:
        m = dict(r)
        p, s, n = r["price_usd"], r["supply"], r["tx_count"]
        mean_v, med_v = r["bc_mean_value"], r["bc_median_value"]
        m["dust_day"] = bool(med_v is not None and p and med_v * p < dust_usd)
        if m["dust_day"]:
            med_v = None
        m["mean_tx_native"] = mean_v
        m["median_tx_native"] = med_v
        m["mean_tx_usd"] = mean_v * p if mean_v is not None and p else None
        m["median_tx_usd"] = med_v * p if med_v is not None and p else None
        m["mean_tx_share_ppm"] = mean_v / s * 1e6 if mean_v is not None and s else None
        m["median_tx_share_ppm"] = med_v / s * 1e6 if med_v is not None and s else None
        m["fee_per_tx_usd"] = r["fees_native"] * p / n if r["fees_native"] is not None and p and n else None
        if m.get("market_cap_usd") is None and p and s:
            m["market_cap_usd"] = p * s
        out.append(m)
    return out


METRIC_KEYS = ["price_usd", "market_cap_usd", "supply", "tx_count", "active_addresses", "fee_per_tx_usd",
               "mean_tx_native", "median_tx_native", "mean_tx_usd", "median_tx_usd",
               "mean_tx_share_ppm", "median_tx_share_ppm"]


def _elasticities(mon: List[dict]) -> dict:
    def e(x, y):
        g = [m for m in mon if m.get(x) and m.get(y)]
        r = log_slope([m[x] for m in g], [m[y] for m in g])
        return {"slope": round(r["slope"], 3), "r2": round(r["r2"], 3), "n": r["n"]} if r else None
    return {
        "mean_native_vs_price": e("price_usd", "mean_tx_native"),
        "median_native_vs_price": e("price_usd", "median_tx_native"),
        "mean_usd_vs_price": e("price_usd", "mean_tx_usd"),
        "median_usd_vs_price": e("price_usd", "median_tx_usd"),
        "mean_share_vs_users": e("active_addresses", "mean_tx_share_ppm"),
        "median_share_vs_users": e("active_addresses", "median_tx_share_ppm"),
        "median_share_vs_market_cap": e("market_cap_usd", "median_tx_share_ppm"),
    }


def summary(chain_key: str) -> dict:
    chain = CHAINS[chain_key]
    rows = daily_metrics(load(chain_key))
    mon = monthly(rows, METRIC_KEYS, start_year=chain.start_year)
    yr = yearly(rows, METRIC_KEYS, start_year=chain.start_year)
    eras = [{"from": str(chain.start_year), "to": str(mon[-1]["month"][:4]), **_elasticities(mon)}]
    if chain.saturation_year:
        pre = [m for m in mon if int(m["month"][:4]) < chain.saturation_year]
        post = [m for m in mon if int(m["month"][:4]) >= chain.saturation_year]
        eras.append({"from": str(chain.start_year), "to": str(chain.saturation_year - 1), **_elasticities(pre)})
        eras.append({"from": str(chain.saturation_year), "to": str(mon[-1]["month"][:4]), **_elasticities(post)})
    dust = {}
    for r in rows:
        y = r["date"].year
        if y >= chain.start_year and r["bc_median_value"] is not None:
            dust.setdefault(y, [0, 0])
            dust[y][0] += 1
            dust[y][1] += int(r["dust_day"])
    dust_share = {y: round(v[1] / v[0], 3) for y, v in dust.items() if v[0]}
    first = next(y for y in yr if y.get("price_usd") and y.get("median_tx_native"))
    last = yr[-1]
    ratios = {k: (last[k] / first[k] if first.get(k) and last.get(k) else None) for k in METRIC_KEYS}
    return {
        "chain": chain.key, "name": chain.name, "symbol": chain.symbol.upper(), "supply_note": chain.supply_note,
        "saturation_year": chain.saturation_year,
        "range": {"first_year": first["year"], "last_year": last["year"], "last_day": rows[-1]["date"].isoformat()},
        "monthly": [{k: (round(m[k], 8) if isinstance(m.get(k), float) else m.get(k)) for k in ["month", *METRIC_KEYS]} for m in mon],
        "yearly": [{k: (round(y[k], 8) if isinstance(y.get(k), float) else y.get(k)) for k in ["year", *METRIC_KEYS]} for y in yr],
        "eras": eras,
        "ratios": {k: (round(v, 4) if v else None) for k, v in ratios.items()},
        "dust_share_by_year": dust_share,
        "dust_threshold_usd": DUST_USD,
    }


def summarize_all(keys: Optional[List[str]] = None) -> List[dict]:
    return [summary(k) for k in (keys or list(CHAINS))]
