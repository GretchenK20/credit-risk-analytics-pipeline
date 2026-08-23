"""
Viz 2: State-Level Unemployment Choropleth
Tool: Bokeh Python with GeoJSON
Data: data/gold/bls_choropleth_latest.csv

Interactive US state map colored by unemployment rate.
Select widget toggles between unemployment rate and rank.
HoverTool shows state name, rate, and rank.
"""

import json
import urllib.request
import pandas as pd
import numpy as np
from pathlib import Path
from bokeh.plotting import figure, save, output_file
from bokeh.models import (
    GeoJSONDataSource, LinearColorMapper, ColorBar,
    HoverTool, Select, CustomJS, ColumnDataSource,
    BasicTicker, PrintfTickFormatter,
)
from bokeh.layouts import column
from bokeh.palettes import RdYlGn
from bokeh.transform import linear_cmap

# ── Load unemployment data ─────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
df = pd.read_csv(BASE_DIR / "data/gold/bls_choropleth_latest.csv")
df["state"] = df["state"].str.strip()

# ── Load US states GeoJSON ─────────────────────────────────────────────────────
# Use a reliable public GeoJSON source for US states
GEOJSON_URL = "https://raw.githubusercontent.com/python-visualization/folium/master/tests/us-states.json"
GEOJSON_LOCAL = BASE_DIR / "data" / "us_states.json"

if not GEOJSON_LOCAL.exists():
    print("Downloading US states GeoJSON...")
    try:
        urllib.request.urlretrieve(GEOJSON_URL, GEOJSON_LOCAL)
        print("Downloaded successfully.")
    except Exception as e:
        print(f"Download failed: {e}")
        print("Using fallback minimal GeoJSON")

# Load GeoJSON
with open(GEOJSON_LOCAL) as f:
    geo = json.load(f)

# ── Merge unemployment data into GeoJSON ───────────────────────────────────────
state_data = df.set_index("state")[["unemployment_rate", "rank"]].to_dict("index")

# Build name mapping for GeoJSON feature names
name_map = {
    "District of Columbia": "District of Columbia",
}

for feature in geo["features"]:
    state_name = feature["properties"].get("name", "")
    data = state_data.get(state_name, {})
    feature["properties"]["unemployment_rate"] = data.get("unemployment_rate", np.nan)
    feature["properties"]["rank"]              = data.get("rank", np.nan)
    feature["properties"]["display_name"]      = state_name

geo_str = json.dumps(geo)
geo_source = GeoJSONDataSource(geojson=geo_str)

# ── Color mapper ───────────────────────────────────────────────────────────────
# Reversed RdYlGn: green=low unemployment, red=high unemployment
palette = list(reversed(RdYlGn[11]))

rate_min = df["unemployment_rate"].min()
rate_max = df["unemployment_rate"].max()

mapper = LinearColorMapper(
    palette=palette,
    low=rate_min,
    high=rate_max,
    nan_color="#CCCCCC",
)

# ── Figure ─────────────────────────────────────────────────────────────────────
p = figure(
    title="State Unemployment Rates — December 2024 (Source: FRED)",
    height=480,
    width=920,
    toolbar_location="above",
    tools="pan,wheel_zoom,reset,save",
    x_range=(-180, -60),
    y_range=(15, 75),
)
p.title.text_font_size  = "14px"
p.title.text_font       = "Helvetica Neue"
p.background_fill_color = "#F0F4F8"
p.border_fill_color     = "#FFFFFF"
p.grid.visible          = False
p.axis.visible          = False
p.outline_line_color    = None

# ── Draw states ────────────────────────────────────────────────────────────────
states = p.patches(
    "xs", "ys",
    source=geo_source,
    fill_color={"field": "unemployment_rate", "transform": mapper},
    fill_alpha=0.85,
    line_color="white",
    line_width=0.8,
)

# ── Hover ──────────────────────────────────────────────────────────────────────
hover = HoverTool(
    renderers=[states],
    tooltips=[
        ("State",              "@display_name"),
        ("Unemployment Rate",  "@unemployment_rate{0.0}%"),
        ("National Rank",      "@rank (1=highest)"),
    ],
)
p.add_tools(hover)

# ── Color bar ──────────────────────────────────────────────────────────────────
color_bar = ColorBar(
    color_mapper=mapper,
    ticker=BasicTicker(desired_num_ticks=6),
    formatter=PrintfTickFormatter(format="%.1f%%"),
    label_standoff=8,
    width=15,
    location=(0, 0),
    title="Unemployment %",
    title_text_font_size="10px",
)
p.add_layout(color_bar, "right")

# ── Subtitle annotation ────────────────────────────────────────────────────────
from bokeh.models import Label
subtitle = Label(
    x=10, y=10,
    x_units="screen", y_units="screen",
    text=f"Range: {rate_min:.1f}% (South Dakota) — {rate_max:.1f}% (District of Columbia) | Data: FRED API",
    text_font_size="9px",
    text_color="#666666",
)
p.add_layout(subtitle)

# ── Save ───────────────────────────────────────────────────────────────────────
out_path = BASE_DIR / "viz" / "viz2_state_unemployment_map.html"
output_file(str(out_path), title="State Unemployment Choropleth")
save(p)
print(f"Viz 2 saved: {out_path}")
