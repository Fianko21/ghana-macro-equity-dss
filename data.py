"""Data layer (annual): ingestion, column mapping, validation, alignment, transformation, provenance."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ANNUAL_FILE = DATA_DIR / "ghana_annual.csv"
STATUS_FILE = DATA_DIR / "annual_status.csv"
STATA_FILE = DATA_DIR / "stata_results.json"

YEAR_ALIASES = ["year", "time", "date", "period", "years"]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def suggest_mapping(columns: list[str]) -> dict[str, str | None]:
    """Suggest which uploaded column feeds each canonical variable (and the year)."""
    normed = {_norm(c): c for c in columns}
    mapping: dict[str, str | None] = {}
    for key in ["year", *config.VARIABLES]:
        cands = [key] + (YEAR_ALIASES if key == "year" else config.VARIABLES[key]["aliases"])
        mapping[key] = next((normed[_norm(a)] for a in cands if _norm(a) in normed), None)
    return mapping


def read_any(file) -> pd.DataFrame:
    name = getattr(file, "name", str(file)).lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    raw = file.read() if hasattr(file, "read") else Path(file).read_bytes()
    return pd.read_csv(io.BytesIO(raw))


def _to_number(s: pd.Series) -> pd.Series:
    if s.dtype.kind in "if":
        return s.astype(float)
    cleaned = s.astype(str).str.replace(r"[,%\s]|GH¢|GHS", "", regex=True).replace({"": np.nan, "nan": np.nan, "..": np.nan, "-": np.nan})
    return pd.to_numeric(cleaned, errors="coerce")


def _to_year(s: pd.Series) -> pd.Series:
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().mean() > 0.8:
        return num.round().astype("Int64")
    return pd.to_datetime(s, errors="coerce").dt.year.astype("Int64")


@dataclass
class QualityReport:
    rows_in: int = 0
    rows_out: int = 0
    start: int = 0
    end: int = 0
    duplicates_collapsed: int = 0
    missing: dict = field(default_factory=dict)
    outliers: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def standardise(raw: pd.DataFrame, mapping: dict[str, str | None]) -> tuple[pd.DataFrame, QualityReport]:
    """Map columns to canonical names, put on a complete annual index, validate and flag anomalies.

    Annual data are NOT interpolated: a missing year stays missing, because filling
    a whole year would invent an observation.
    """
    rep = QualityReport(rows_in=len(raw))
    if not mapping.get("year"):
        raise ValueError("No year column was identified. Map a column to 'year'.")
    missing_req = [k for k in config.REQUIRED if not mapping.get(k)]
    if missing_req:
        raise ValueError("Required variable(s) not mapped: " + ", ".join(label(k) for k in missing_req))

    df = pd.DataFrame({"year": _to_year(raw[mapping["year"]])})
    for key in config.VARIABLES:
        if mapping.get(key):
            df[key] = _to_number(raw[mapping[key]]).values
    bad = int(df["year"].isna().sum())
    if bad:
        rep.warnings.append(f"{bad} row(s) dropped because the year could not be read.")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    before = len(df)
    df = df.groupby("year").last()
    rep.duplicates_collapsed = before - len(df)

    df = df.loc[(df.index >= config.STUDY_START) & (df.index <= config.STUDY_END)]
    if df.empty:
        raise ValueError(f"No rows fall inside the study window {config.STUDY_START}-{config.STUDY_END}.")
    df = df.reindex(range(df.index.min(), df.index.max() + 1))
    df.index.name = "year"

    for col in df.columns:
        rep.missing[col] = int(df[col].isna().sum())
        ch = analysis_form(df[[col]])[col]
        scale = max(1.4826 * (ch - ch.median()).abs().median(), 0.5 * ch.std())
        if scale and scale > 0:
            z = (ch - ch.median()) / scale
            flagged = [int(y) for y in z[z.abs() > 3.5].index]
            if flagged:
                rep.outliers[col] = flagged
    rep.rows_out = len(df)
    rep.start, rep.end = int(df.index.min()), int(df.index.max())
    return df, rep


# ----------------------------------------------------------------------------- bundled data
def load_default() -> tuple[pd.DataFrame, QualityReport]:
    raw = pd.read_csv(ANNUAL_FILE)
    return standardise(raw, suggest_mapping(list(raw.columns)))


def load_stata_results() -> dict | None:
    import json
    return json.loads(STATA_FILE.read_text(encoding="utf-8")) if STATA_FILE.exists() else None


def load_status() -> pd.DataFrame | None:
    return pd.read_csv(STATUS_FILE) if STATUS_FILE.exists() else None


# ----------------------------------------------------------------------------- metadata helpers
def meta(key: str) -> dict:
    return config.VARIABLES.get(key, {"label": key, "unit": "", "transform": "diff", "group": "macro",
                                      "core": False, "analyse": False, "source": ""})


def label(key: str) -> str:
    return meta(key)["label"]


def unit(key: str) -> str:
    return meta(key)["unit"]


def transform_kind(key: str) -> str:
    return meta(key)["transform"]


def analysis_form(df: pd.DataFrame) -> pd.DataFrame:
    """Convert each variable to the form used for relationship analysis.

    none   -> used as is (returns, inflation, growth rates)
    diff   -> x_t - x_{t-1} (percentage points)
    logret -> 100 * ln(x_t / x_{t-1}) (percent change; for the exchange rate = depreciation)
    """
    out = pd.DataFrame(index=df.index)
    for col in df.columns:
        k = transform_kind(col)
        if k == "none":
            out[col] = df[col]
        elif k == "logret":
            s = df[col].where(df[col] > 0)
            out[col] = 100 * np.log(s / s.shift(1))
        else:
            out[col] = df[col].diff()
    return out


def form_label(key: str) -> str:
    k = transform_kind(key)
    if k == "none":
        return label(key)
    if key == "usd_ghs":
        return "Cedi depreciation (% change in GH¢/US$)"
    return ("% change in " if k == "logret" else "Change in ") + label(key)


def period_of(year: int) -> str:
    for p in config.PERIODS:
        if p["start"] <= year <= p["end"]:
            return p["name"]
    return "Other"
