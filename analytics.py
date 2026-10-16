"""Analytical engine (annual): descriptives, correlation, lead-lag, stationarity, eras and alerts."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import adfuller

import config
from dss.data import label, period_of


# ----------------------------------------------------------------------------- descriptives
def describe(df: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for c in df.columns:
        s = df[c].dropna()
        if len(s) < 3:
            continue
        jb = stats.jarque_bera(s) if len(s) >= 8 else None
        rows[label(c)] = {
            "N": len(s), "Mean": s.mean(), "Median": s.median(), "Std. dev.": s.std(),
            "Min": s.min(), "Max": s.max(), "Skewness": stats.skew(s),
            "Excess kurtosis": stats.kurtosis(s), "Jarque-Bera p": jb.pvalue if jb else np.nan,
        }
    return pd.DataFrame(rows).T


def by_period(levels: pd.DataFrame) -> pd.DataFrame:
    """Equity performance and average macro conditions in each historical era."""
    out = []
    for p in config.PERIODS:
        lv = levels.loc[p["start"]:p["end"]]
        if lv.empty:
            continue
        row = {"Era": p["name"], "Years": f"{lv.index.min()}-{lv.index.max()}", "N": len(lv)}
        if "gse_return" in lv:
            r = lv["gse_return"].dropna() / 100
            row["Cumulative GSE return (%)"] = 100 * (np.prod(1 + r) - 1)
            row["Average annual GSE return (%)"] = 100 * r.mean()
            row["Volatility of returns (%)"] = 100 * r.std()
            row["Years with negative return"] = int((r < 0).sum())
        for c in ["inflation", "policy_rate", "tbill_91", "real_tbill", "gdp_growth", "mc_gdp"]:
            if c in lv:
                row[f"Avg {label(c)}"] = lv[c].mean()
        if "usd_ghs" in lv:
            fx = lv["usd_ghs"].dropna()
            # depreciation measured from the year before the era starts, when available
            base = levels["usd_ghs"].get(p["start"] - 1, np.nan)
            base = base if base == base else fx.iloc[0]
            row["Cedi depreciation over era (%)"] = 100 * (fx.iloc[-1] / base - 1)
        out.append(row)
    return pd.DataFrame(out).set_index("Era")


# ----------------------------------------------------------------------------- correlation
def corr_with_pvalues(df: pd.DataFrame, method: str = "pearson") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cols = list(df.columns)
    r = pd.DataFrame(np.nan, index=cols, columns=cols)
    p, n = r.copy(), r.copy()
    f = stats.pearsonr if method == "pearson" else stats.spearmanr
    for i, a in enumerate(cols):
        for b in cols[i:]:
            pair = df[[a, b]].dropna()
            if len(pair) < 6:
                continue
            if a == b:
                r.loc[a, b], p.loc[a, b], n.loc[a, b] = 1.0, 0.0, len(pair)
                continue
            res = f(pair[a], pair[b])
            r.loc[a, b] = r.loc[b, a] = res[0]
            p.loc[a, b] = p.loc[b, a] = res[1]
            n.loc[a, b] = n.loc[b, a] = len(pair)
    return r, p, n


def rolling_corr(df: pd.DataFrame, x: str, y: str, window: int) -> pd.Series:
    return df[x].rolling(window, min_periods=max(5, window - 2)).corr(df[y])


def lead_lag(df: pd.DataFrame, equity: str, macro: str, max_lag: int) -> pd.DataFrame:
    """Correlation between equity variable in year t and macro variable in year t-k (k>0: macro leads)."""
    rows = []
    for k in range(-max_lag, max_lag + 1):
        pair = pd.concat([df[equity], df[macro].shift(k)], axis=1).dropna()
        if len(pair) < 8:
            continue
        r, p = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
        rows.append({"Lag (k)": k, "Correlation": r, "p-value": p, "N": len(pair),
                     "Bound (±2/√N)": 2 / np.sqrt(len(pair))})
    return pd.DataFrame(rows)


def ols_line(x: pd.Series, y: pd.Series) -> dict:
    pair = pd.concat([x, y], axis=1).dropna()
    res = stats.linregress(pair.iloc[:, 0], pair.iloc[:, 1])
    return {"slope": res.slope, "intercept": res.intercept, "r2": res.rvalue ** 2, "p": res.pvalue, "n": len(pair)}


def correlation_by_period(form: pd.DataFrame, equity: str, macros: list[str], min_n: int = 4) -> pd.DataFrame:
    tbl = {}
    for p in config.PERIODS:
        sub = form.loc[p["start"]:p["end"]]
        tbl[p["name"]] = {label(m): sub[[equity, m]].dropna().corr().iloc[0, 1]
                          if len(sub[[equity, m]].dropna()) >= min_n else np.nan for m in macros}
    return pd.DataFrame(tbl)


# ----------------------------------------------------------------------------- stationarity
def adf_table(levels: pd.DataFrame, form: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in levels.columns:
        row = {"Variable": label(c)}
        for name, frame in [("Level", levels), ("Analysis form", form)]:
            s = frame[c].dropna()
            if len(s) < 15 or s.nunique() < 3:
                row[f"{name}: ADF stat"], row[f"{name}: p-value"] = np.nan, np.nan
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                stat, p, *_ = adfuller(s, autolag="AIC", maxlag=3)
            row[f"{name}: ADF stat"], row[f"{name}: p-value"] = stat, p
        lp, fp = row["Level: p-value"], row["Analysis form: p-value"]
        row["Verdict"] = ("Stationary in levels" if lp == lp and lp < 0.05
                          else "Stationary in analysis form" if fp == fp and fp < 0.05
                          else "Inconclusive (short sample)")
        rows.append(row)
    return pd.DataFrame(rows).set_index("Variable")


# ----------------------------------------------------------------------------- monitoring
RATE_LIKE = {"inflation", "policy_rate", "tbill_91", "tbill_91_dec", "real_tbill", "gdp_growth",
             "gse_return", "mc_gdp", "trade_gdp", "gfcf_gdp", "turnover_ratio"}


def latest_snapshot(levels: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in levels.columns:
        s = levels[c].dropna()
        if len(s) < 2:
            continue
        last, prev = s.iloc[-1], s.iloc[-2]
        rate = c in RATE_LIKE
        rows.append({
            "key": c, "Indicator": label(c), "Latest": last, "Year": int(s.index[-1]),
            "1Y change": (last - prev) if rate else 100 * (last / prev - 1),
            "10Y average": s.iloc[-10:].mean(), "change_unit": "pp" if rate else "%",
        })
    return pd.DataFrame(rows)


def alerts(levels: pd.DataFrame) -> list[dict]:
    a, cfg, out = levels, config.ALERTS, []
    yr = int(a.index.max())
    if "gse_return" in a and a["gse_return"].notna().any():
        r = a["gse_return"].dropna().iloc[-1]
        if cfg["equity_negative_return"] and r < 0:
            out.append({"level": "warning", "text": f"The GSE index fell {r:.1f}% in {yr}."})
        if abs(r) >= cfg["equity_large_move_pct"]:
            out.append({"level": "info", "text": f"Exceptional market year: GSE return of {r:+.1f}% in {yr}."})
    if "inflation" in a:
        v = a["inflation"].dropna().iloc[-1]
        if v >= cfg["inflation_threshold_pct"]:
            out.append({"level": "warning", "text": f"Inflation is high at {v:.1f}% (threshold {cfg['inflation_threshold_pct']:.0f}%)."})
    if "usd_ghs" in a:
        s = a["usd_ghs"].dropna()
        dep = 100 * (s.iloc[-1] / s.iloc[-2] - 1)
        if dep >= cfg["fx_depreciation_pct"]:
            out.append({"level": "warning", "text": f"The cedi depreciated {dep:.1f}% against the US$ (annual average)."})
        elif dep < 0:
            out.append({"level": "info", "text": f"The cedi appreciated {abs(dep):.1f}% against the US$ (annual average)."})
    if cfg.get("negative_real_rate") and "real_tbill" in a and a["real_tbill"].notna().any():
        v = a["real_tbill"].dropna().iloc[-1]
        if v < 0:
            out.append({"level": "info", "text": f"Real T-bill rate is negative ({v:.1f}%): bills lose value after inflation, which tends to favour equities."})
    if "tbill_91" in a and a["tbill_91"].notna().sum() > 1:
        s = a["tbill_91"].dropna()
        d = s.iloc[-1] - s.iloc[-2]
        if abs(d) >= cfg.get("tbill_change_pp", 5.0):
            out.append({"level": "info", "text": f"91-day T-bill rate {'fell' if d < 0 else 'rose'} by {abs(d):.1f} pp to {s.iloc[-1]:.1f}% (annual average) in {yr}."})
        if "inflation" in a:
            real = s.iloc[-1] - a["inflation"].dropna().iloc[-1]
            if real < 0:
                out.append({"level": "info", "text": f"T-bill rate is below inflation (real return {real:.1f}%), which tends to favour equities."})
    if not out:
        out.append({"level": "ok", "text": f"No monitoring rules triggered for {yr}."})
    return out


def regime(levels: pd.DataFrame, year: int | None = None) -> str:
    """Macro regime from the direction of inflation and the T-bill rate versus the previous year."""
    lv = levels if year is None else levels.loc[:year]

    def d(c):
        s = lv[c].dropna() if c in lv else pd.Series(dtype=float)
        return np.sign(s.iloc[-1] - s.iloc[-2]) if len(s) > 1 else 0
    infl, rate = d("inflation"), d("tbill_91")
    if infl < 0 and rate < 0:
        return "Easing: falling inflation and falling yields (supportive for equities)"
    if infl > 0 and rate > 0:
        return "Tightening: rising inflation and rising yields (headwind for equities)"
    if infl > 0 and rate <= 0:
        return "Inflation pressure: rising inflation without higher yields (real rates falling)"
    return "Mixed: falling inflation with steady or rising yields"


def regime_history(levels: pd.DataFrame) -> pd.Series:
    years = [y for y in levels.index if y > levels.index.min()]
    return pd.Series([regime(levels, y).split(":")[0] for y in years], index=years)


def tag_periods(index) -> pd.Series:
    return pd.Series([period_of(int(y)) for y in index], index=index)
