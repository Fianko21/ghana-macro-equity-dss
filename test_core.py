"""Checks of the data and analytical layers (annual edition).  Run: python -m pytest tests"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dss import analytics as A  # noqa: E402
from dss import data as D  # noqa: E402


def test_bundled_dataset_loads():
    lv, rep = D.load_default()
    assert rep.start == 1993 and rep.end == 2025 and rep.rows_out == 33
    assert list(lv.columns) == ["gse_return", "mc_gdp", "inflation", "tbill_91", "usd_ghs", "gdp_growth"]


def test_returns_reproduce_published_index_levels():
    lv, _ = D.load_default()
    idx = 1000 * (1 + lv.loc[2011:, "gse_return"] / 100).cumprod()   # GSE-CI base: 31 Dec 2010 = 1000
    assert abs(idx[2018] - 2572.2) < 2      # BoG Dec-2018 GSE-CI
    assert abs(idx[2025] - 8770.25) < 2     # GSE Dec-2025 GSE-CI


def test_analysis_forms():
    idx = pd.Index([2000, 2001, 2002], name="year")
    lv = pd.DataFrame({"gse_return": [10.0, -5.0, 20.0], "tbill_91": [20.0, 25.0, 22.0],
                       "usd_ghs": [1.0, 1.1, 1.21]}, index=idx)
    f = D.analysis_form(lv)
    assert f["gse_return"].tolist() == [10.0, -5.0, 20.0]
    assert f["tbill_91"].iloc[1:].tolist() == [5.0, -3.0]
    assert np.isclose(f["usd_ghs"].iloc[1], 100 * np.log(1.1))


def test_column_mapping_aliases():
    m = D.suggest_mapping(["Time", "Stock return", "Inflation", "GDP growth ", "Exchange rate", "91-day"])
    assert m["year"] == "Time" and m["gse_return"] == "Stock return" and m["inflation"] == "Inflation"
    assert m["gdp_growth"] == "GDP growth " and m["usd_ghs"] == "Exchange rate" and m["tbill_91"] == "91-day"


def test_no_interpolation_of_missing_years():
    lv, rep = D.load_default()
    # no variable is filled by interpolation: the only filled T-bill years (1993-94) are documented imputations
    assert rep.missing["tbill_91"] == 0 and lv.loc[1994, "tbill_91"] == 29.50


def test_lead_lag_recovers_known_lag():
    rng = np.random.default_rng(1)
    idx = pd.Index(range(1950, 2030))
    x = pd.Series(rng.normal(size=80), index=idx)
    df = pd.DataFrame({"eq": x.shift(1) + 0.1 * rng.normal(size=80), "m": x})
    ll = A.lead_lag(df, "eq", "m", 3)
    assert ll.loc[ll["Correlation"].idxmax(), "Lag (k)"] == 1


def test_eras_cover_study_period():
    lv, _ = D.load_default()
    bp = A.by_period(lv)
    assert bp["N"].sum() == 33
    assert abs(bp.loc["5. DDEP crisis & recovery", "Cumulative GSE return (%)"] - 100 * (8770.25 / 2789.3 - 1)) < 1
