import datetime as dt
import math

import pytest

from pasta.analysis import bitcoin as b


def test_log_slope_recovers_power_law():
    xs = [1, 2, 4, 8, 16]
    ys = [10 * x ** -1.0 for x in xs]
    e = b.log_slope(xs, ys)
    assert e["slope"] == pytest.approx(-1.0)
    assert e["r2"] == pytest.approx(1.0)
    assert b.log_slope([1, 2], [1, 2]) is None            # too few points
    assert b.log_slope([0, 1, 2], [1, 1, 1]) is None      # zeros dropped -> too few


def test_daily_metrics_and_supply_adjustment():
    rows = [{"date": dt.date(2020, 1, 1), "price_usd": 10.0, "tx_count": 100.0, "est_volume_btc": 50.0,
             "est_volume_usd": 500.0, "supply_btc": 1_000_000.0, "active_addresses": 5.0, "fees_usd": 10.0,
             "output_volume_btc": 80.0},
            {"date": dt.date(2020, 1, 2), "price_usd": None, "tx_count": 0.0, "est_volume_btc": 1.0,
             "est_volume_usd": None, "supply_btc": None, "active_addresses": None, "fees_usd": None,
             "output_volume_btc": None}]
    m = b.daily_metrics(rows)
    assert m[0]["mean_tx_btc"] == 0.5
    assert m[0]["mean_tx_usd"] == 5.0
    assert m[0]["mean_tx_share_ppm"] == pytest.approx(0.5)      # 0.5 BTC of 1M = 0.5 ppm
    assert m[0]["market_cap_usd"] == 10_000_000.0
    assert m[0]["fee_per_tx_usd"] == 0.1
    assert m[1]["mean_tx_btc"] is None and m[1]["market_cap_usd"] is None


def test_monthly_median_skips_missing_and_early_years():
    rows = [{"date": dt.date(2010, 5, 1), "v": 1.0}, {"date": dt.date(2011, 5, 1), "v": 1.0},
            {"date": dt.date(2011, 5, 2), "v": 3.0}, {"date": dt.date(2011, 5, 3), "v": None}]
    mon = b.monthly(rows, ["v"])
    assert mon == [{"month": "2011-05", "v": 2.0}]


def test_fixed_supply_toy_is_inverse():
    toy = b.fixed_supply_toy([10, 20, 100])
    assert toy["price_rel"] == [1.0, 2.0, 10.0]
    assert toy["coins_per_tx_rel"] == [1.0, 0.5, 0.1]


def test_committed_dataset_supports_the_headline_claims():
    """The slim CSV in data/ is the reproducibility anchor; check its shape and the headline numbers."""
    rows = b.load()
    assert rows[0]["date"] == dt.date(2009, 1, 3)
    assert len(rows) > 6000
    s = b.summary(rows)
    r = s["ratios_first_to_last_year"]
    assert r["price_usd"] > 1000                 # price up by more than 1000x since 2011
    assert r["supply_btc"] == pytest.approx(3.0, abs=0.2)
    assert r["mean_tx_btc"] < 0.05               # coins per tx fell more than 20x
    assert r["mean_tx_share_ppm"] < r["mean_tx_btc"]   # supply adjustment makes the fall larger
    assert r["mean_tx_usd"] > 10                 # but the real size of a transaction rose
    e = s["elasticity"]
    assert -0.7 < e["tx_btc_vs_price"]["slope"] < -0.2
    assert e["tx_share_vs_active_addresses"]["slope"] < -0.8
    assert not math.isnan(e["tx_usd_vs_price"]["r2"])
