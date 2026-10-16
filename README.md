# Ghana Macro-Equity Decision Support System (annual edition, 1993-2025)

An interactive Streamlit dashboard for monitoring and analysing the Ghana Stock Exchange (GSE)
alongside key macroeconomic indicators, using annual data from 1993 to 2025. Built for an MSc capstone project.

## Quick start
```bash
pip install -r requirements.txt
streamlit run app.py          # opens http://localhost:8501
python -m pytest tests        # optional: run the checks
```

## Variables used in the study (Tier 1)
The dashboard and analysis use five variables (set in `config.py`): **gse_return** (dependent), **inflation**,
**tbill_91**, **usd_ghs** (used as cedi depreciation) and **gdp_growth**, plus **mc_gdp** (market capitalisation, % of GDP)
as a display-only context variable that is not used in the correlation or regression analysis. The file `data/ghana_annual_tier1.csv` holds them.
The full compiled dataset below is kept for reference.

## Full compiled dataset (data/ghana_annual.csv)
| Variable | Description | Source |
|---|---|---|
| gse_return | GSE index return, % per year (All-Share Index to 2010, Composite Index from 2011) | SEC Ghana and Bank of Ghana annual reports; CFA Institute; BoG data summaries |
| gse_index | Chain-linked GSE index level (31 Dec 2010 = 1000) | Derived from gse_return |
| mc_gdp | Market capitalisation, % of GDP | World Bank WDI (RESEARCH DATA 3.xlsx; 2025 from current WDI) |
| turnover_ratio, listed_companies | Liquidity and market breadth | World Bank WDI |
| inflation | CPI inflation, annual % | World Bank WDI |
| policy_rate | Monetary policy rate (prime rate before 2002), end of year | Bank of Ghana, via GSS StatsBank |
| tbill_91 / tbill_91_dec | 91-day T-bill rate: annual average / end of year | Bank of Ghana, via GSS StatsBank; SEC Ghana (1993-94) |
| real_tbill | tbill_91 minus inflation | Derived |
| usd_ghs | Official exchange rate, GH¢ per US$, annual average | World Bank WDI (PA.NUS.FCRF) |
| gdp_growth, reer, trade_gdp, gfcf_gdp, pli | Growth and structural context | World Bank WDI |

The source of every value is listed in `data/annual_status.csv` and shown in the dashboard's **Data & quality** tab.

## Files
| Path | Purpose |
|---|---|
| `app.py` | Presentation layer: the dashboard (Overview, Trends, Relationships, Eras & statistics, Data & quality, About) |
| `dss/data.py` | Data layer: reading files, column mapping, annual alignment, anomaly flags, analysis transformations |
| `dss/analytics.py` | Analytical layer: statistics, ADF tests, correlations, lead-lag, eras, regimes and alerts |
| `config.py` | Configuration layer: variables, study window, historical eras, alert thresholds |
| `data/raw/` | Compiled source tables with their citations |
| `scripts/build_annual_dataset.py` | Rebuilds `data/ghana_annual.csv` and `data/annual_status.csv` from `data/raw/` |
| `scripts/download_data.py` | Downloads WDI and GSS StatsBank data on your own computer, so you can verify or refresh the inputs |
| `archive_monthly/` | The earlier monthly (2019-2026) version of the dataset, kept for reference only |

## Refreshing or checking the data
```bash
python scripts/download_data.py          # World Bank WDI + GSS StatsBank interest rates
python scripts/build_annual_dataset.py   # rebuild the analysis dataset
```

## Known data notes
- **GSE index:** the All-Share Index (to 2010) and the Composite Index (from 2011) are linked through annual returns.
  The linked series reproduces the published GSE-CI levels for Dec 2018 (2,572) and Dec 2025 (8,770).
- **Market cap (% of GDP), 2012-2018:** taken from RESEARCH DATA 3.xlsx. These years are not in the current WDI release.
- **Policy rate and 91-day T-bill rate, 1993-1994:** the policy rate is missing and the T-bill rate is end-of-year only.
- **2025 values:** these come from the latest releases and may be revised.

## Deploying (free)
Push the folder to GitHub, then deploy it on https://share.streamlit.io with `app.py` as the entry point.

## Scope
Descriptive and associative analysis only: no forecasting, no trading signals. This is not investment advice.
