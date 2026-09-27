import datetime as dt
import os

import pytest

from pasta.analysis import chains as ch


def test_chain_registry_is_well_formed():
    for key, c in ch.CHAINS.items():
        assert c.key == key and c.unit > 1 and c.start_year >= 2011
        assert c.field in ("output_total", "value")


def test_daily_metrics_derivations():
    rows = [{"date": dt.date(2021, 1, 1), "price_usd": 2.0, "supply": 1_000_000.0, "tx_count": 1000.0,
             "active_addresses": 10.0, "fees_native": 5.0, "market_cap_usd": None,
             "bc_tx_count": 1000.0, "bc_sum_value": 5000.0, "bc_median_value": 2.5, "bc_mean_value": 5.0}]
    m = ch.daily_metrics(rows)[0]
    assert m["mean_tx_usd"] == 10.0 and m["median_tx_usd"] == 5.0
    assert m["mean_tx_share_ppm"] == pytest.approx(5.0)
    assert m["median_tx_share_ppm"] == pytest.approx(2.5)
    assert m["fee_per_tx_usd"] == pytest.approx(0.01)
    assert m["market_cap_usd"] == 2_000_000.0
    assert m["dust_day"] is False


def test_dust_days_are_excluded_from_median_metrics():
    rows = [{"date": dt.date(2024, 1, 1), "price_usd": 0.1, "supply": 1e9, "tx_count": 10.0, "active_addresses": 1.0,
             "fees_native": 0.0, "market_cap_usd": None, "bc_tx_count": 10.0, "bc_sum_value": 1.0,
             "bc_median_value": 0.001, "bc_mean_value": 0.1}]     # median worth $0.0001
    m = ch.daily_metrics(rows)[0]
    assert m["dust_day"] is True
    assert m["median_tx_native"] is None and m["median_tx_usd"] is None and m["median_tx_share_ppm"] is None
    assert m["mean_tx_usd"] == pytest.approx(0.01)


@pytest.mark.parametrize("key", [k for k in ch.CHAINS if os.path.exists(ch.csv_path(k))])
def test_committed_chain_datasets_load_and_summarize(key):
    s = ch.summary(key)
    assert s["range"]["first_year"] >= ch.CHAINS[key].start_year
    assert len(s["monthly"]) > 24
    assert s["eras"][0]["median_native_vs_price"] is not None
    assert s["ratios"]["price_usd"] is not None and s["ratios"]["price_usd"] > 0
