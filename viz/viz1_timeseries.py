"""
Viz 1: Credit Stress Time Series Dashboard
Tool: Bokeh Python
Data: data/gold/quarterly_mart_latest.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path
from bokeh.plotting import figure, save, output_file
from bokeh.models import (
    ColumnDataSource, RangeSlider, CheckboxGroup,
    HoverTool, Span, Label, CustomJS,
    DatetimeTickFormatter, Div,
)
from bokeh.layouts import column, row

# ── Load data ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
df = pd.read_csv(BASE_DIR / "data/gold/quarterly_mart_latest.csv", parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)

for col in ["delinquency_all", "chargeoff_credit_card", "fed_funds_rate"]:
    df[col] = df[col].interpolate(method="linear")

# Add quarter label for hover
df["quarter_label"] = (
    df["date"].dt.year.astype(str) + " Q" +
    df["date"].dt.quarter.astype(str)
)

# Bokeh needs ms timestamps for datetime axis
df["date_ms"] = df["date"].astype(np.int64) // 10**6

COLORS = {
    "delinquency": "#E8474C",
    "chargeoff":   "#F4A225",
    "fed_funds":   "#2166AC",
}

source_full = ColumnDataSource(df)
source_view = ColumnDataSource(df.copy())

# ── Figure ─────────────────────────────────────────────────────────────────────
p = figure(
    title="U.S. Consumer Credit Stress Indicators (2014–2024)",
    x_axis_type="datetime",
    height=420, width=900,
    toolbar_location="above",
    tools="pan,wheel_zoom,box_zoom,reset,save",
)
p.title.text_font_size      = "15px"
p.background_fill_color     = "#FAFAFA"
p.border_fill_color         = "#FFFFFF"
p.grid.grid_line_color      = "#E0E0E0"
p.xaxis.formatter = DatetimeTickFormatter(months="%b %Y", years="%Y")
p.yaxis.axis_label = "Rate (%)"
p.xaxis.axis_label = "Quarter"

# ── Lines ──────────────────────────────────────────────────────────────────────
l1 = p.line("date", "delinquency_all", source=source_view,
            line_color=COLORS["delinquency"], line_width=2.5,
            legend_label="Consumer Loan Delinquency Rate")
c1 = p.circle("date", "delinquency_all", source=source_view,
              color=COLORS["delinquency"], size=5, alpha=0.7)

l2 = p.line("date", "chargeoff_credit_card", source=source_view,
            line_color=COLORS["chargeoff"], line_width=2.5,
            legend_label="Credit Card Charge-Off Rate")
c2 = p.circle("date", "chargeoff_credit_card", source=source_view,
              color=COLORS["chargeoff"], size=5, alpha=0.7)

l3 = p.line("date", "fed_funds_rate", source=source_view,
            line_color=COLORS["fed_funds"], line_width=2.5,
            line_dash="dashed", legend_label="Federal Funds Rate")
c3 = p.circle("date", "fed_funds_rate", source=source_view,
              color=COLORS["fed_funds"], size=5, alpha=0.7)

# ── Hover ──────────────────────────────────────────────────────────────────────
hover = HoverTool(
    renderers=[c1, c2, c3],
    tooltips=[
        ("Quarter",        "@quarter_label"),
        ("Delinquency",    "@delinquency_all{0.00}%"),
        ("Charge-Off",     "@chargeoff_credit_card{0.00}%"),
        ("Fed Funds Rate", "@fed_funds_rate{0.00}%"),
        ("Rate Regime",    "@rate_regime"),
    ],
)
p.add_tools(hover)

# ── Event spans ────────────────────────────────────────────────────────────────
events = [
    ("2020-03-15", "COVID-19\nOnset",      "#888888"),
    ("2022-03-15", "Fed Rate\nHike Cycle", "#555555"),
    ("2023-03-10", "SVB\nCollapse",        "#AA3333"),
]
for date_str, label_text, color in events:
    event_ms = pd.Timestamp(date_str).value // 10**6
    p.add_layout(Span(location=event_ms, dimension="height",
                      line_color=color, line_dash="dashed",
                      line_width=1.5, line_alpha=0.7))
    p.add_layout(Label(x=event_ms, y=0.3, x_units="data", y_units="data",
                       text=label_text, text_font_size="9px",
                       text_color=color, text_alpha=0.85))

# ── Legend ─────────────────────────────────────────────────────────────────────
p.legend.location              = "top_right"
p.legend.click_policy          = "hide"
p.legend.background_fill_alpha = 0.85
p.legend.label_text_font_size  = "10px"

# ── RangeSlider — use actual date strings for title, ms for values ─────────────
date_min = int(df["date_ms"].min())
date_max = int(df["date_ms"].max())

# Build human-readable date labels for start/end
date_labels = {
    int(row["date_ms"]): row["quarter_label"]
    for _, row in df.iterrows()
}

# Separate Div for human-readable date label (avoids Bokeh appending raw ms values)
date_label = Div(
    text=f"<b>Date Range:</b> {df['quarter_label'].iloc[0]} — {df['quarter_label'].iloc[-1]}",
    styles={"font-size": "13px", "margin-bottom": "2px", "color": "#333333"},
    width=860,
)

slider = RangeSlider(
    start=date_min,
    end=date_max,
    value=(date_min, date_max),
    step=int(90 * 24 * 60 * 60 * 1000),
    title="",
    width=860,
    stylesheets=["""
        .bk-slider-title { display: none !important; }
        .bk-input-group .bk-slider-value { display: none !important; }
        .noUi-tooltip { display: none !important; }
        .bk-Slider .bk-widget-box { padding-top: 0px; }
    """],
)

# CustomJS: filter source_view AND update slider title with readable dates
callback = CustomJS(
    args=dict(source_full=source_full, source_view=source_view,
              slider=slider, date_labels=date_labels, date_label=date_label),
    code="""
    const lo   = slider.value[0];
    const hi   = slider.value[1];
    const full = source_full.data;
    const view = {};

    for (const key of Object.keys(full)) { view[key] = []; }

    for (let i = 0; i < full['date_ms'].length; i++) {
        const t = full['date_ms'][i];
        if (t >= lo && t <= hi) {
            for (const key of Object.keys(full)) {
                view[key].push(full[key][i]);
            }
        }
    }

    source_view.data = view;
    source_view.change.emit();

    // Update title with readable quarter labels
    function fmtDate(ms) {
        const d = new Date(ms);
        const y = d.getFullYear();
        const m = d.getMonth();
        const q = Math.floor(m / 3) + 1;
        return y + ' Q' + q;
    }
    date_label.text = '<b>Date Range:</b> ' + fmtDate(lo) + ' — ' + fmtDate(hi);
""")

slider.js_on_change("value", callback)

# ── Checkboxes ─────────────────────────────────────────────────────────────────
checkbox = CheckboxGroup(
    labels=["Delinquency Rate", "Charge-Off Rate", "Fed Funds Rate"],
    active=[0, 1, 2],
    width=200,
)
checkbox_cb = CustomJS(
    args=dict(l1=l1, c1=c1, l2=l2, c2=c2, l3=l3, c3=c3, cb=checkbox),
    code="""
        const a = cb.active;
        l1.visible = a.includes(0); c1.visible = a.includes(0);
        l2.visible = a.includes(1); c2.visible = a.includes(1);
        l3.visible = a.includes(2); c3.visible = a.includes(2);
    """
)
checkbox.js_on_change("active", checkbox_cb)

# ── Layout & save ──────────────────────────────────────────────────────────────
layout = column(p, date_label, slider, row(checkbox))

out_path = BASE_DIR / "viz" / "viz1_credit_stress_timeseries.html"
output_file(str(out_path), title="Credit Stress Time Series")
save(layout)
print(f"Viz 1 saved: {out_path}")
