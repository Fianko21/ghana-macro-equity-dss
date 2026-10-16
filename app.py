"""Ghana Macro-Equity Decision Support System - annual edition (1993-2025).

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import config
from dss import analytics as A
from dss import data as D

st.set_page_config(page_title="Ghana Macro-Equity DSS", page_icon="📈", layout="wide")

EQUITY_COLOR, MACRO_COLOR, NEG_COLOR = "#1565C0", "#E65100", "#C62828"
ERA_COLORS = ["#78909C", "#1E88E5", "#FB8C00", "#43A047", "#E53935"]
PLOT_CFG = {"displaylogo": False, "toImageButtonOptions": {"format": "png", "scale": 2}}


# ============================================================================ data loading
@st.cache_data(show_spinner=False)
def _cell(v):
    """Format a table cell as text so mixed number/blank columns display cleanly."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
        return f"{v:.3f}"
    return str(v)


def _bundled():
    return D.load_default()


def get_data():
    st.sidebar.header("Data")
    src = st.sidebar.radio("Annual dataset", ["Bundled (Ghana, 1993-2025)", "Upload my own file"],
                           help="Uploaded files are processed in memory only and are not stored.")
    if src.startswith("Bundled"):
        lv, rep = _bundled()
        return lv, rep, "bundled"
    up = st.sidebar.file_uploader("CSV or Excel, one row per year", type=["csv", "xlsx", "xls"])
    if up is None:
        st.info("Upload a file in the sidebar, or switch back to the bundled dataset.")
        st.stop()
    raw = D.read_any(up)
    sugg = D.suggest_mapping(list(raw.columns))
    with st.sidebar.expander("Column mapping", expanded=True):
        opts = ["(none)"] + list(raw.columns)
        mapping = {}
        for key in ["year", *config.VARIABLES]:
            lab = "Year" if key == "year" else D.label(key)
            default = opts.index(sugg[key]) if sugg.get(key) in opts else 0
            choice = st.selectbox(lab, opts, index=default, key=f"map_{key}")
            mapping[key] = None if choice == "(none)" else choice
    try:
        lv, rep = D.standardise(raw, mapping)
    except ValueError as e:
        st.error(str(e))
        st.stop()
    return lv, rep, "upload"


levels_all, report, source = get_data()
form_all = D.analysis_form(levels_all)

st.sidebar.header("Analysis window")
yrs = list(levels_all.index)
start, end = st.sidebar.select_slider("Years", options=yrs, value=(yrs[0], yrs[-1]))
levels = levels_all.loc[start:end]
form = form_all.loc[start:end]
st.sidebar.caption(f"{len(levels)} annual observations selected.")
show_core_only = False  # the study uses only the five Tier 1 variables in config.py
show_periods = st.sidebar.checkbox("Shade historical eras on charts", value=True)


def vars_for(group=None, analyse=None):
    out = []
    for k in levels_all.columns:
        m = D.meta(k)
        if group and m["group"] != group:
            continue
        if analyse is not None and m.get("analyse") != analyse:
            continue
        if show_core_only and not m.get("core"):
            continue
        out.append(k)
    return out


equity_cols = vars_for("equity")
macro_cols = vars_for("macro")
an_equity = vars_for("equity", True)
an_macro = vars_for("macro", True)


def shade(fig, **kw):
    if not show_periods:
        return fig
    for p in config.PERIODS:
        a, b = max(p["start"], start), min(p["end"], end)
        if a <= b:
            fig.add_vrect(x0=a - 0.5, x1=b + 0.5, fillcolor=p["color"], line_width=0, layer="below",
                          annotation_text=p["name"].split(". ")[0], annotation_position="top left",
                          annotation_font_size=10, **kw)
    return fig


def fmt(v, d=2):
    return "–" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:,.{d}f}"


# ============================================================================ header
st.title("Ghana Macro-Equity Decision Support System")
st.caption(f"Annual monitoring and analysis of the Ghana Stock Exchange and the macroeconomy, "
           f"{levels_all.index.min()}-{levels_all.index.max()}. Prototype for a capstone project. "
           f"This is an analytical tool, not investment advice.")

tabs = st.tabs(["Overview", "Trends", "Relationships", "Eras & statistics", "Econometric results", "Data & quality", "About"])

# ============================================================================ 1. OVERVIEW
with tabs[0]:
    snap = A.latest_snapshot(levels)
    last_year = int(levels.index.max())
    st.subheader(f"Snapshot: {last_year}")
    order = ["gse_return", "mc_gdp", "inflation", "tbill_91", "usd_ghs", "gdp_growth"]
    tiles = [r for k in order for _, r in snap[snap.key == k].iterrows()]
    for i in range(0, len(tiles), 3):
        cols = st.columns(3)
        for c, r in zip(cols, tiles[i:i + 3]):
            inverse = r["key"] in {"inflation", "usd_ghs", "tbill_91"}
            c.metric(r["Indicator"], fmt(r["Latest"], 0 if r["key"] == "gse_index" else 2),
                     f"{r['1Y change']:+.2f} {r['change_unit']} vs {r['Year'] - 1}",
                     delta_color="inverse" if inverse else "normal",
                     help=f"10-year average: {fmt(r['10Y average'])}. Unit: {D.unit(r['key'])}.")

    left, right = st.columns([2, 1])
    with left:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=levels.index, y=levels["gse_return"], name="GSE return (%)",
                             marker_color=np.where(levels["gse_return"] >= 0, EQUITY_COLOR, NEG_COLOR), opacity=0.85))
        if "inflation" in levels:
            fig.add_trace(go.Scatter(x=levels.index, y=levels["inflation"], name="Inflation (%)",
                                     line=dict(color=MACRO_COLOR, width=2.5)), secondary_y=False)
        if "tbill_91" in levels:
            fig.add_trace(go.Scatter(x=levels.index, y=levels["tbill_91"], name="91-day T-bill (%)",
                                     line=dict(color=MACRO_COLOR, dash="dot", width=2)), secondary_y=False)
        fig.update_layout(height=430, title="GSE annual return vs inflation and T-bill rate",
                          legend=dict(orientation="h", y=-0.15), margin=dict(t=60, b=10), bargap=0.25)
        fig.update_yaxes(title_text="%", secondary_y=False)
        st.plotly_chart(shade(fig), width="stretch", config=PLOT_CFG)
    with right:
        st.markdown(f"**Macro regime in {last_year}**")
        st.info(A.regime(levels))
        st.markdown("**Monitoring alerts**")
        for a in A.alerts(levels):
            {"warning": st.warning, "info": st.info, "ok": st.success}[a["level"]](a["text"])
        st.caption("Alert thresholds are set in config.py (ALERTS).")

    cum = 100 * (1 + levels["gse_return"].fillna(0) / 100).cumprod()
    fig = go.Figure(go.Scatter(x=levels.index, y=cum, line=dict(color=EQUITY_COLOR, width=2.5), name="Cumulative return"))
    fig.update_layout(height=320, title=f"Growth of GH¢100 invested in the GSE index at the start of {start} (log scale)",
                      yaxis_type="log", margin=dict(t=50, b=10))
    st.plotly_chart(shade(fig), width="stretch", config=PLOT_CFG)

# ============================================================================ 2. TRENDS
with tabs[1]:
    st.subheader("Compare an equity indicator with a macro indicator")
    c1, c2, c3 = st.columns(3)
    eq = c1.selectbox("Equity indicator", equity_cols, format_func=D.label)
    mac = c2.selectbox("Macro indicator", macro_cols, format_func=D.label,
                       index=macro_cols.index("inflation") if "inflation" in macro_cols else 0)
    mode = c3.radio("Display", ["Levels (dual axis)", "Rebased to 100"], horizontal=True)
    if mode.startswith("Levels"):
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=levels.index, y=levels[eq], name=D.label(eq), mode="lines+markers",
                                 line=dict(color=EQUITY_COLOR, width=2.5)))
        fig.add_trace(go.Scatter(x=levels.index, y=levels[mac], name=D.label(mac), mode="lines+markers",
                                 line=dict(color=MACRO_COLOR, width=2)), secondary_y=True)
        fig.update_yaxes(title_text=f"{D.label(eq)} ({D.unit(eq)})", secondary_y=False)
        fig.update_yaxes(title_text=f"{D.label(mac)} ({D.unit(mac)})", secondary_y=True)
    else:
        rb = levels[[eq, mac]].apply(lambda s: 100 * s / s.dropna().iloc[0])
        fig = px.line(rb, x=rb.index, y=[eq, mac], markers=True, color_discrete_sequence=[EQUITY_COLOR, MACRO_COLOR])
        fig.for_each_trace(lambda t: t.update(name=D.label(t.name)))
        fig.update_yaxes(title_text=f"Index (first year = 100)")
        st.caption("Rebasing is meaningful for levels (index, exchange rate); for rates and returns use the dual-axis view.")
    fig.update_layout(height=470, legend=dict(orientation="h", y=-0.15), xaxis_title=None, margin=dict(t=30))
    st.plotly_chart(shade(fig), width="stretch", config=PLOT_CFG)

    st.markdown("**Year-on-year form used in the relationship analysis**")
    fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                         subplot_titles=[D.form_label(eq), D.form_label(mac)])
    fig2.add_trace(go.Bar(x=form.index, y=form[eq], marker_color=np.where(form[eq] >= 0, EQUITY_COLOR, NEG_COLOR)), 1, 1)
    fig2.add_trace(go.Bar(x=form.index, y=form[mac], marker_color=MACRO_COLOR), 2, 1)
    fig2.update_layout(height=420, showlegend=False, margin=dict(t=40))
    st.plotly_chart(fig2, width="stretch", config=PLOT_CFG)

# ============================================================================ 3. RELATIONSHIPS
with tabs[2]:
    st.subheader("How do macro conditions relate to equity performance?")
    st.caption("Variables enter in their *analysis form*: returns, inflation and GDP growth as they are; interest rates "
               "and ratios as year-on-year changes (pp); the exchange rate as % depreciation. This avoids spurious "
               "correlation between trending series. With about 30 annual observations, a correlation must exceed "
               "roughly ±0.36 to be significant at 5%.")
    c1, c2 = st.columns([1, 3])
    method = c1.radio("Correlation method", ["pearson", "spearman"], format_func=str.title)
    basis = c1.radio("Basis", ["Analysis form (recommended)", "Levels"])
    cols_used = an_equity + an_macro
    frame = (form if basis.startswith("Analysis") else levels)[cols_used]
    r, p, n = A.corr_with_pvalues(frame, method)
    labs = [D.form_label(c) if basis.startswith("Analysis") else D.label(c) for c in r.columns]
    stars = p.map(lambda v: "***" if v < 0.01 else "**" if v < 0.05 else "*" if v < 0.10 else "")
    fig = go.Figure(go.Heatmap(z=r.values, x=labs, y=labs, zmin=-1, zmax=1, colorscale="RdBu",
                               text=(r.round(2).astype(str) + stars).values, texttemplate="%{text}",
                               customdata=n.values, hovertemplate="%{y} / %{x}<br>r = %{z:.3f}<br>N = %{customdata}<extra></extra>"))
    fig.update_layout(height=600, margin=dict(t=30), yaxis_autorange="reversed")
    c2.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    c2.caption("Significance: * p<0.10, ** p<0.05, *** p<0.01. Correlation does not imply causation.")

    st.divider()
    c1, c2 = st.columns(2)
    eq = c1.selectbox("Equity variable", an_equity, format_func=D.form_label, key="rel_eq")
    mac = c2.selectbox("Macro variable", an_macro, format_func=D.form_label, key="rel_mac")

    a1, a2 = st.columns(2)
    with a1:
        sc = form[[mac, eq]].dropna().assign(Era=lambda d: A.tag_periods(d.index), Year=lambda d: d.index)
        fig = px.scatter(sc, x=mac, y=eq, color="Era", hover_name="Year",
                         color_discrete_map={pp["name"]: c for pp, c in zip(config.PERIODS, ERA_COLORS)},
                         labels={mac: D.form_label(mac), eq: D.form_label(eq)})
        ols = A.ols_line(form[mac], form[eq])
        xs = np.linspace(sc[mac].min(), sc[mac].max(), 50)
        fig.add_trace(go.Scatter(x=xs, y=ols["intercept"] + ols["slope"] * xs, mode="lines", name="OLS fit",
                                 line=dict(color="black", dash="dash")))
        fig.update_layout(height=440, title=f"R² = {ols['r2']:.3f}, slope p = {ols['p']:.3f}, n = {ols['n']}",
                          legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    with a2:
        win = st.slider("Rolling window (years)", 6, 15, config.ROLLING_WINDOW_DEFAULT)
        rc = A.rolling_corr(form, eq, mac, win)
        fig = go.Figure(go.Scatter(x=rc.index, y=rc, mode="lines+markers", line=dict(color="#6A1B9A", width=2)))
        fig.add_hline(y=0, line_color="grey")
        fig.update_layout(height=440, yaxis=dict(range=[-1, 1], title="Correlation"),
                          title=f"{win}-year rolling correlation (plotted at window end)", margin=dict(t=60))
        st.plotly_chart(shade(fig), width="stretch", config=PLOT_CFG)

    b1, b2 = st.columns(2)
    with b1:
        ll = A.lead_lag(form, eq, mac, config.MAX_LAG)
        if not ll.empty:
            fig = go.Figure(go.Bar(x=ll["Lag (k)"], y=ll["Correlation"],
                                   marker_color=np.where(ll["Correlation"].abs() > ll["Bound (±2/√N)"], NEG_COLOR, "#90A4AE"),
                                   customdata=ll[["p-value", "N"]],
                                   hovertemplate="k=%{x}<br>r=%{y:.3f}<br>p=%{customdata[0]:.3f}<br>N=%{customdata[1]}<extra></extra>"))
            bound = ll["Bound (±2/√N)"].mean()
            for y in (bound, -bound):
                fig.add_hline(y=y, line_dash="dot", line_color="grey")
            fig.update_layout(height=380, title="Lead-lag cross-correlation",
                              xaxis_title="k (years): k > 0 means the macro variable leads", yaxis_title="Correlation", margin=dict(t=60))
            st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
            st.caption("Red bars exceed the approximate 95% band (±2/√N).")
    with b2:
        st.markdown("**Correlation with the selected equity variable, by era**")
        tbl = A.correlation_by_period(form, eq, an_macro)
        st.dataframe(tbl.style.format("{:.2f}", na_rep="–").background_gradient(cmap="RdBu", vmin=-1, vmax=1),
                     width="stretch")
        st.caption("Each era has only 4-8 years, so these are descriptive indications, not significance tests.")

# ============================================================================ 4. ERAS & STATISTICS
with tabs[3]:
    st.subheader("Historical eras")
    bp = A.by_period(levels_all)
    st.dataframe(bp.T.apply(lambda col: col.map(lambda v: f"{v:,.2f}" if isinstance(v, (float, np.floating)) else str(v))),
                 width="stretch")
    st.caption("Era boundaries are set in config.py (PERIODS). Cumulative returns compound the annual returns.")

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(bp.reset_index(), x="Era", y="Average annual GSE return (%)", color="Era",
                     color_discrete_sequence=ERA_COLORS)
        fig.update_layout(height=380, showlegend=False, title="Average GSE return by era", xaxis_title=None)
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    with c2:
        rh = A.regime_history(levels_all)
        dfr = pd.DataFrame({"Regime": rh, "GSE return": levels_all["gse_return"].reindex(rh.index)}).dropna()
        agg = dfr.groupby("Regime")["GSE return"].agg(["mean", "median", "count"]).reset_index()
        fig = px.bar(agg, x="Regime", y="mean", text="count",
                     color="Regime", color_discrete_map={"Easing": "#43A047", "Tightening": NEG_COLOR,
                                                         "Inflation pressure": "#FB8C00",
                                                         "Mixed": "#78909C"})
        fig.update_traces(texttemplate="n=%{text}", textposition="outside")
        fig.update_layout(height=380, showlegend=False, title="Average GSE return by macro regime",
                          yaxis_title="Mean annual return (%)", xaxis_title=None)
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

    st.subheader("Descriptive statistics")
    which = st.radio("Series", ["Analysis form", "Levels"], horizontal=True)
    st.dataframe(A.describe((form if which == "Analysis form" else levels)[vars_for()]).style.format("{:.3f}"), width="stretch")

    st.subheader("Stationarity (Augmented Dickey-Fuller)")
    adf = A.adf_table(levels[vars_for()], form[vars_for()])
    st.dataframe(adf.style.format("{:.3f}", na_rep="–", subset=[c for c in adf.columns if c != "Verdict"]), width="stretch")
    st.caption("H0: unit root. p < 0.05 rejects H0. Lag length by AIC (max 3). ADF tests have low power with ~30 annual observations.")

    st.subheader("Distribution of annual GSE returns")
    fig = px.histogram(levels.assign(Era=A.tag_periods(levels.index)), x="gse_return", color="Era", nbins=20,
                       color_discrete_sequence=ERA_COLORS, labels={"gse_return": "Annual GSE return (%)"})
    fig.update_layout(height=360, bargap=0.05)
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

# ============================================================================ 5. ECONOMETRIC RESULTS (Stata)
def _stars(p):
    return "" if p is None else "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


with tabs[4]:
    R = D.load_stata_results()
    if R is None:
        st.info("No econometric results file found (data/stata_results.json).")
    else:
        st.subheader("Econometric results (estimated in Stata)")
        st.caption(f"Source: {R['meta']['source']}. {R['meta']['dataset']}. "
                   "These results are fixed outputs of the Stata analysis and do not change with the sidebar filters.")
        a = R["ardl"]
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Bounds test F", f"{a['bounds']['F']:.2f}", help=f"1% I(1) critical value: {a['bounds']['F_crit_I1_1']}")
        k2.metric("Bounds test t", f"{a['bounds']['t']:.2f}", help=f"1% I(1) critical value: {a['bounds']['t_crit_I1_1']}")
        k3.metric("Error-correction term", f"{a['ect'][0]:.2f}***")
        k4.metric("ARDL adjusted R²", f"{a['adj_r2']:.2f}", help=f"{a['spec']}, {a['sample']}, N = {a['n']}")
        st.success(
            "**Key findings.** (1) The variables are a mix of I(0) and I(1) and none is I(2), so the ARDL bounds approach is valid. "
            "(2) The bounds test rejects 'no long-run relationship' at the 1% level: GSE returns and the macro variables are linked in the long run. "
            "(3) In the short run, a rise in the 91-day T-bill rate is the most consistent negative influence on returns: about -2.3 to -3.1 "
            "percentage points of return per 1-point rise in the OLS models (significant at 10% in most specifications, 5% in robust regression) "
            "and -5.3 in the ARDL model (1%). (4) Same-year OLS models explain little of the variation (R² 0.05-0.26); the dynamic ARDL model explains far more.")

        st.markdown("#### 1. Stationarity (unit-root) tests")
        ur = pd.DataFrame(R["unit_root"]).rename(columns={
            "variable": "Variable", "adf": "ADF", "adf_p": "ADF p", "pp": "PP", "pp_p": "PP p", "dfgls_lag1": "DF-GLS (lag 1)",
            "kpss_lag2": "KPSS (lag 2)", "d_adf": "ADF, 1st diff.", "d_adf_p": "p (diff.)", "za_t": "Zivot-Andrews t",
            "za_break": "Break year", "za_reject": "ZA rejects at", "order": "Order of integration"})
        st.dataframe(ur.style.format({c: "{:.3f}" for c in ["ADF", "ADF p", "PP", "PP p", "DF-GLS (lag 1)", "KPSS (lag 2)",
                                                             "ADF, 1st diff.", "p (diff.)", "Zivot-Andrews t"]}),
                     width="stretch", hide_index=True)
        st.caption(R["unit_root_notes"] + " The T-bill rate is I(1) by conventional tests but stationary around a 2004 break (Zivot-Andrews).")

        st.markdown("#### 2. Short-run regressions and robustness checks (dependent variable: GSE return)")
        specs = R["ols_specs"]
        tb = [(sp["name"], *sp["coef"]["ΔT-bill rate"]) for sp in specs if "ΔT-bill rate" in sp["coef"]]
        dfp = pd.DataFrame(tb, columns=["Specification", "coef", "se", "p"])
        fig = go.Figure(go.Scatter(x=dfp["coef"], y=dfp["Specification"], mode="markers",
                                   marker=dict(size=11, color=np.where(dfp["p"] < 0.10, NEG_COLOR, "#90A4AE")),
                                   error_x=dict(type="data", array=1.96 * dfp["se"], color="#607D8B"),
                                   customdata=dfp["p"], hovertemplate="%{y}<br>coef = %{x:.2f}<br>p = %{customdata:.3f}<extra></extra>"))
        fig.add_vline(x=0, line_color="grey", line_dash="dot")
        fig.update_layout(height=360, title="Effect of a 1-point rise in the T-bill rate on the GSE return (pp), with approx. 95% CI",
                          xaxis_title="Coefficient on ΔT-bill rate", yaxis_autorange="reversed", margin=dict(t=60, l=10))
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
        st.caption("Red = significant at 10% or better. Error bars are ±1.96 standard errors (approximate).")

        names = []
        for sp in specs:
            for v in sp["coef"]:
                if v not in names:
                    names.append(v)
        tbl = {}
        for sp in specs:
            col = {}
            for v in names:
                c = sp["coef"].get(v)
                col[v] = f"{c[0]:.3f}{_stars(c[2])} ({c[1]:.3f})" if c else ""
            col["N"] = str(sp["n"])
            col["R²"] = "" if sp["r2"] is None else f"{sp['r2']:.3f}"
            col["F-test p"] = f"{sp['f_p']:.3f}"
            tbl[sp["name"]] = col
        st.dataframe(pd.DataFrame(tbl), width="stretch")
        st.caption("Coefficient (standard error). * p<0.10, ** p<0.05, *** p<0.01.")
        st.markdown("**Diagnostics of the baseline model**")
        st.dataframe(pd.DataFrame(R["ols_diagnostics"]).rename(columns=str.capitalize).map(_cell), width="stretch", hide_index=True)

        st.markdown(f"#### 3. Long-run relationship: {a['spec']} model with bounds test")
        c1, c2 = st.columns([3, 2])
        with c1:
            lr = pd.DataFrame([(k, *v) for k, v in a["long_run"].items()], columns=["Variable", "coef", "se", "p", "lo", "hi"])
            fig = go.Figure(go.Bar(x=lr["coef"], y=lr["Variable"], orientation="h",
                                   marker_color=np.where(lr["p"] < 0.05, EQUITY_COLOR, "#90A4AE"),
                                   error_x=dict(type="data", symmetric=False, array=lr["hi"] - lr["coef"], arrayminus=lr["coef"] - lr["lo"]),
                                   customdata=lr["p"], hovertemplate="%{y}<br>coef = %{x:.2f}<br>p = %{customdata:.3f}<extra></extra>"))
            fig.add_vline(x=0, line_color="grey")
            fig.update_layout(height=330, title="Long-run coefficients (95% CI from Stata)", margin=dict(t=50, l=10),
                              yaxis_autorange="reversed")
            st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
        with c2:
            b = a["bounds"]
            st.dataframe(pd.DataFrame({
                "Statistic": ["F", "t"], "Value": [b["F"], b["t"]],
                "5% I(1) bound": [b["F_crit_I1_5"], b["t_crit_I1_5"]], "1% I(1) bound": [b["F_crit_I1_1"], b["t_crit_I1_1"]],
                "p-value (I(1))": [b["p_F_I1"], b["p_t_I1"]]}), width="stretch", hide_index=True)
            st.caption(f"Pesaran, Shin and Smith (2001) bounds test with Kripfganz and Schneider (2020) critical values. "
                       f"Decision: {b['decision']}.")
            st.dataframe(pd.DataFrame(a["diagnostics"]).rename(columns=str.capitalize), width="stretch", hide_index=True)
        sr = pd.DataFrame([(k, *v) for k, v in a["short_run"].items()], columns=["Term", "Coefficient", "Std. error", "p-value"])
        sr.loc[len(sr)] = ["Error-correction term (adjustment)", *a["ect"]]
        sr["Sig."] = sr["p-value"].map(_stars)
        st.markdown("**Short-run (error-correction) coefficients**")
        st.dataframe(sr.style.format({"Coefficient": "{:.3f}", "Std. error": "{:.3f}", "p-value": "{:.3f}"}), width="stretch", hide_index=True)
        st.caption("The error-correction coefficient of -1.50 is negative and significant, confirming adjustment to the long-run "
                   "relationship; a value below -1 means returns overshoot and oscillate around equilibrium, which is typical "
                   "for a dependent variable that is itself I(0). With 31 observations and 13 estimated parameters, these "
                   "long-run estimates should be read with caution.")

# ============================================================================ 5. DATA & QUALITY
with tabs[5]:
    st.subheader("Data quality report")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Years", report.rows_out)
    q2.metric("Coverage", f"{report.start}-{report.end}")
    q3.metric("Missing values", sum(report.missing.values()))
    q4.metric("Series with flagged years", len(report.outliers))
    for w in report.warnings:
        st.warning(w)
    miss = pd.DataFrame([{"Variable": D.label(k), "Missing years": v,
                          "Which": ", ".join(str(y) for y in levels_all.index[levels_all[k].isna()])}
                         for k, v in report.missing.items() if v])
    if not miss.empty:
        with st.expander("Missing values"):
            st.dataframe(miss, width="stretch", hide_index=True)
    if report.outliers:
        with st.expander("Unusually large values in analysis form (flagged for checking, not removed)"):
            st.dataframe(pd.DataFrame([{"Variable": D.label(k), "Years": ", ".join(map(str, v))}
                                       for k, v in report.outliers.items()]), width="stretch", hide_index=True)

    status = D.load_status() if source == "bundled" else None
    if status is not None:
        st.subheader("Source of every value")
        var = st.selectbox("Variable", [v for v in config.VARIABLES if v in set(status["variable"])], format_func=D.label)
        st.dataframe(status[status["variable"] == var].drop(columns="variable"), width="stretch", hide_index=True)
        st.download_button("Download full provenance table (CSV)", status.to_csv(index=False), "annual_status.csv")

    st.subheader("Data dictionary")
    dd = [{"Variable": k, "Label": v["label"], "Group": v["group"], "Core": "Yes" if v["core"] else "",
           "Unit": v["unit"], "Source": v["source"],
           "Analysis form": {"none": "as is", "diff": "Δx (pp)", "logret": "100·Δln(x)"}[v["transform"]],
           "Role": ("dependent" if k == "gse_return" else "context (display only)" if not v["analyse"] else "explanatory"),
           "Years available": int(levels_all[k].notna().sum()) if k in levels_all else 0}
          for k, v in config.VARIABLES.items()]
    st.dataframe(pd.DataFrame(dd), width="stretch", hide_index=True)

    st.subheader("Export")
    e1, e2 = st.columns(2)
    e1.download_button("Download selected years: levels (CSV)", levels.to_csv(), "ghana_annual_levels.csv")
    e2.download_button("Download selected years: analysis form (CSV)", form.to_csv(), "ghana_annual_analysis_form.csv")

# ============================================================================ 6. ABOUT
with tabs[6]:
    st.markdown(f"""
### About this prototype
A **data-driven decision support system** that brings Ghana Stock Exchange performance and key macroeconomic
variables together for monitoring and analysis over {config.STUDY_START}-{config.STUDY_END}.

**Architecture (four layers)**
1. **Data layer**: compiles annual data from the World Bank WDI, Bank of Ghana (via Ghana Statistical Service StatsBank),
   SEC Ghana and GSE publications. It chain-links the GSE All-Share and Composite indices, maps columns, puts
   the data on a complete annual index, flags anomalies and records the source of every value.
2. **Analytical layer**: descriptive statistics, ADF tests, Pearson and Spearman correlations, rolling and lead-lag
   correlations, comparison of historical eras, macro-regime classification and rule-based alerts.
3. **Presentation layer**: an interactive Streamlit dashboard with Plotly charts.
4. **Configuration layer**: config.py holds the variables, study window, eras and alert thresholds.

**Scope limits:** no forecasting, no trading signals and no live data feed. Results are descriptive and associative.
""")
