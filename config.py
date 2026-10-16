"""Central configuration (Tier 1 variables: GSE return, inflation, 91-day T-bill rate,
exchange rate, real GDP growth) for the Ghana Macro-Equity Decision Support System (annual edition).

Edit this file (not the app code) to change variables, the study window, the historical eras
or the alert thresholds. Chapter 3 refers to this file as "the configuration layer".
"""

# ---------------------------------------------------------------------------
# 1. Variables (annual)
#   label     : what users see
#   group     : "equity" or "macro"
#   core      : True = one of the main variables of the study (shown by default)
#   unit      : display unit
#   source    : publisher
#   transform : how the variable enters the relationship analysis
#               "none"   = used as is (already a rate of change, e.g. returns, inflation, growth)
#               "diff"   = first difference, in percentage points (interest rates, ratios)
#               "logret" = 100 x ln(x_t / x_t-1), percent change (index levels, exchange rate)
#   analyse   : include in correlation / relationship analysis
#   aliases   : column names auto-matched when a user uploads a file
# ---------------------------------------------------------------------------
VARIABLES = {
    # ---------------- dependent variable (equity market performance)
    "gse_return": {
        "label": "GSE index return", "group": "equity", "core": True, "unit": "% per year",
        "source": "GSE / SEC Ghana / Bank of Ghana", "transform": "none", "analyse": True,
        "aliases": ["gse return", "stock return", "market return", "gse_ci_return", "return"],
    },
    # ---------------- context variable (display only: not used in the correlation / regression analysis)
    "mc_gdp": {
        "label": "Market capitalisation (% of GDP)", "group": "equity", "core": True, "unit": "% of GDP",
        "source": "World Bank WDI (CM.MKT.LCAP.GD.ZS); 2012-2018 from RESEARCH DATA 3.xlsx",
        "transform": "diff", "analyse": False,
        "aliases": ["mc", "market capitalization", "market capitalisation", "mcap", "market cap"],
    },
    # ---------------- explanatory variables (macroeconomy)
    "inflation": {
        "label": "Inflation (CPI, annual %)", "group": "macro", "core": True, "unit": "%",
        "source": "World Bank WDI (FP.CPI.TOTL.ZG)", "transform": "none", "analyse": True,
        "aliases": ["inflation rate", "cpi inflation", "inflation (%)"],
    },
    "tbill_91": {
        "label": "91-day T-bill rate (annual average)", "group": "macro", "core": True, "unit": "% p.a.",
        "source": "Bank of Ghana (via GSS StatsBank)", "transform": "diff", "analyse": True,
        "aliases": ["91-day", "tbill", "t-bill", "treasury bill rate", "tbr", "interest rate"],
    },
    "usd_ghs": {
        "label": "Exchange rate (GH¢ per US$, average)", "group": "macro", "core": True, "unit": "GH¢/US$",
        "source": "World Bank WDI (PA.NUS.FCRF)", "transform": "logret", "analyse": True,
        "aliases": ["exchange rate", "usd/ghs", "ghs/usd", "fx", "official exchange rate"],
    },
    "gdp_growth": {
        "label": "Real GDP growth", "group": "macro", "core": True, "unit": "%",
        "source": "World Bank WDI (NY.GDP.MKTP.KD.ZG)", "transform": "none", "analyse": True,
        "aliases": ["gdp growth", "gdp growth (%)", "growth"],
    },
}

REQUIRED = ["gse_return", "inflation"]

# ---------------------------------------------------------------------------
# 2. Study window and historical eras (inclusive years)
# ---------------------------------------------------------------------------
STUDY_START = 1993
STUDY_END = 2025

PERIODS = [
    {"name": "1. Early market & high inflation", "start": 1993, "end": 2000, "color": "rgba(120,144,156,0.14)"},
    {"name": "2. Stabilisation & HIPC boom", "start": 2001, "end": 2008, "color": "rgba(30,136,229,0.10)"},
    {"name": "3. Oil era & fiscal stress", "start": 2009, "end": 2016, "color": "rgba(251,140,0,0.12)"},
    {"name": "4. Recovery & COVID-19", "start": 2017, "end": 2021, "color": "rgba(67,160,71,0.12)"},
    {"name": "5. DDEP crisis & recovery", "start": 2022, "end": 2025, "color": "rgba(229,57,53,0.12)"},
]

# ---------------------------------------------------------------------------
# 3. Monitoring rules, evaluated on the latest year in the data
# ---------------------------------------------------------------------------
ALERTS = {
    "equity_negative_return": True,      # flag a negative GSE return
    "equity_large_move_pct": 50.0,       # |annual return| at or above this
    "inflation_threshold_pct": 15.0,     # inflation above this
    "fx_depreciation_pct": 15.0,         # cedi loses this % or more against US$ in a year
    "tbill_change_pp": 5.0,              # T-bill rate moved by this much or more in a year
}

ROLLING_WINDOW_DEFAULT = 10   # years, for rolling correlations
MAX_LAG = 3                   # years, for lead-lag cross-correlations
