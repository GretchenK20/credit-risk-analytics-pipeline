"""
Viz 3 (Bokeh version): Macro Correlation Scatter
Tool: Bokeh Python
Data: data/gold/scatter_mart_latest.csv

Unemployment rate (X) vs Delinquency rate (Y)
Color = interest rate regime
Size = consumer credit outstanding (normalized)
Tableau is the PRIMARY delivery of this viz — this is the Bokeh backup.

Run this to generate the HTML version; import scatter_mart_latest.csv
into Tableau for the polished version.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from bokeh.plotting import figure, save, output_file
from bokeh.models import (
    ColumnDataSource, HoverTool, ColorBar,
    CategoricalColorMapper, Legend, LegendItem,
    Label, Span, Select, CustomJS,
)
from bokeh.layouts import column
from bokeh.palettes import Category10
from bokeh.transform import factor_cmap

# ── Load data ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
df = pd.read_csv(BASE_DIR / "data/gold/scatter_mart_latest.csv", parse_dates=["date"])

# Drop rows missing key fields
df = df.dropna(subset=["unemployment_rate", "delinquency_all"])

# Normalize consumer credit for bubble size (px range 8-28)
if "consumer_credit_outstanding" in df.columns and df["consumer_credit_outstanding"].notna().any():
    cc = df["consumer_credit_outstanding"].fillna(df["consumer_credit_outstanding"].median())
    df["bubble_size"] = 8 + 20 * (cc - cc.min()) / (cc.max() - cc.min() + 1e-9)
else:
    df["bubble_size"] = 14

# Ensure rate_regime exists
if "rate_regime" not in df.columns:
    df["rate_regime"] = "Unknown"

df["rate_regime"] = df["rate_regime"].fillna("Unknown")

# Unique regimes for color mapping
regimes = ["Ultra-Low (<1%)", "Low (1-3%)", "Moderate (3-5%)", "High (5%+)", "Unknown"]
regimes = [r for r in regimes if r in df["rate_regime"].unique()]

palette = ["#2166AC", "#74ADD1", "#F4A225", "#E8474C", "#AAAAAA"][:len(regimes)]

# Format tooltip date
df["date_str"] = df["date"].dt.strftime("%Y Q") + df["date"].dt.quarter.astype(str)
if "quarter_label" in df.columns:
    df["date_str"] = df["quarter_label"]

source = ColumnDataSource(df)

# ── Figure ─────────────────────────────────────────────────────────────────────
p = figure(
    title="Unemployment Rate vs. Consumer Loan Delinquency (2014–2024)",
    x_axis_label="Unemployment Rate (%)",
    y_axis_label="Consumer Loan Delinquency Rate (%)",
    height=480,
    width=720,
    toolbar_location="above",
    tools="pan,wheel_zoom,box_zoom,reset,save",
)
p.title.text_font_size  = "14px"
p.title.text_font       = "Helvetica Neue"
p.background_fill_color = "#FAFAFA"
p.border_fill_color     = "#FFFFFF"
p.grid.grid_line_color  = "#E8E8E8"

# ── Scatter points ─────────────────────────────────────────────────────────────
scatter = p.circle(
    x="unemployment_rate",
    y="delinquency_all",
    source=source,
    size="bubble_size",
    color=factor_cmap("rate_regime", palette=palette, factors=regimes),
    alpha=0.75,
    line_color="white",
    line_width=0.8,
)

# ── Hover ──────────────────────────────────────────────────────────────────────
hover = HoverTool(
    renderers=[scatter],
    tooltips=[
        ("Quarter",              "@date_str"),
        ("Unemployment",         "@unemployment_rate{0.0}%"),
        ("Delinquency Rate",     "@delinquency_all{0.00}%"),
        ("Fed Funds Rate",       "@fed_funds_rate{0.00}%"),
        ("Rate Regime",          "@rate_regime"),
        ("Consumer Credit",      "@consumer_credit_outstanding{$0,0}B"),
    ],
)
p.add_tools(hover)

# ── Manual legend ──────────────────────────────────────────────────────────────
from bokeh.plotting import figure as bk_figure
for regime, color in zip(regimes, palette):
    p.circle([], [], color=color, alpha=0.75, size=10, legend_label=regime)

p.legend.title          = "Rate Regime"
p.legend.location       = "top_left"
p.legend.click_policy   = "hide"
p.legend.background_fill_alpha = 0.85
p.legend.label_text_font_size  = "10px"

# ── Reference lines ────────────────────────────────────────────────────────────
# National unemployment "full employment" threshold (~4%)
span_unemp = Span(
    location=4.0, dimension="height",
    line_color="#888888", line_dash="dashed",
    line_width=1.2, line_alpha=0.6,
)
p.add_layout(span_unemp)
lbl_unemp = Label(
    x=4.05, y=df["delinquency_all"].max() * 0.95,
    text="~Full Employment\nThreshold (4%)",
    text_font_size="9px", text_color="#888888",
)
p.add_layout(lbl_unemp)

# ── Subtitle ───────────────────────────────────────────────────────────────────
subtitle = Label(
    x=10, y=10,
    x_units="screen", y_units="screen",
    text="Bubble size = Total Consumer Credit Outstanding | Color = Fed Funds Rate Regime | Source: FRED",
    text_font_size="9px", text_color="#666666",
)
p.add_layout(subtitle)

# ── Select filter by rate regime ───────────────────────────────────────────────
source_full = ColumnDataSource(df)

select = Select(
    title="Filter by Rate Regime:",
    value="All",
    options=["All"] + regimes,
    width=220,
)

select_cb = CustomJS(
    args=dict(source=source, source_full=source_full, select=select),
    code="""
        const val  = select.value;
        const full = source_full.data;
        const out  = {};

        for (const key of Object.keys(full)) {
            out[key] = [];
        }

        for (let i = 0; i < full['rate_regime'].length; i++) {
            if (val === 'All' || full['rate_regime'][i] === val) {
                for (const key of Object.keys(full)) {
                    out[key].push(full[key][i]);
                }
            }
        }

        source.data = out;
        source.change.emit();
    """
)
select.js_on_change("value", select_cb)

# ── Layout & save ──────────────────────────────────────────────────────────────
layout = column(select, p)

out_path = BASE_DIR / "viz" / "viz3_macro_scatter.html"
output_file(str(out_path), title="Macro Correlation Scatter")
save(layout)
print(f"Viz 3 saved: {out_path}")
