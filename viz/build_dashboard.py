"""
Dashboard: Combined HTML Dashboard
Combines all 7 EDA matplotlib figures + 3 interactive Bokeh visualizations
into a single self-contained HTML file.

Run AFTER:
    python viz/eda.py
    python viz/viz1_timeseries.py
    python viz/viz2_choropleth.py
    python viz/viz3_scatter.py

Output: viz/dashboard.html
"""

import base64
import re
from pathlib import Path
from bokeh.embed import file_html
from bokeh.resources import CDN

BASE_DIR  = Path(__file__).parent.parent
EDA_DIR   = BASE_DIR / "data" / "eda"
VIZ_DIR   = BASE_DIR / "viz"


# ── Helper: encode PNG to base64 for inline embedding ─────────────────────────
def img_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ── Helper: extract Bokeh script+div from saved HTML ──────────────────────────
def extract_bokeh(html_path: Path) -> tuple[str, str]:
    """Extract <script> and <div> blocks from a saved Bokeh HTML file."""
    content = html_path.read_text(encoding="utf-8")

    # Extract all script tags
    scripts = re.findall(r'<script[^>]*>.*?</script>', content, re.DOTALL)
    # Filter to Bokeh data/app scripts (exclude CDN links)
    bokeh_scripts = [s for s in scripts if "Bokeh.embed" in s or '"roots"' in s or "application/json" in s]

    # Extract the root div
    divs = re.findall(r'<div[^>]*class="[^"]*bk-root[^"]*"[^>]*>.*?</div>', content, re.DOTALL)
    if not divs:
        divs = re.findall(r'<div[^>]*id="[^"]*"[^>]*>\s*</div>', content, re.DOTALL)

    script_block = "\n".join(bokeh_scripts)
    div_block    = divs[0] if divs else ""
    return script_block, div_block


# ── Load EDA images ────────────────────────────────────────────────────────────
eda_figures = [
    ("Fig 1: Variable Distributions",              "eda_fig1_distributions.png"),
    ("Fig 2: Correlation Matrix",                  "eda_fig2_correlation_matrix.png"),
    ("Fig 3: Time Series with Rolling Statistics", "eda_fig3_timeseries_rolling.png"),
    ("Fig 4: Scatter Matrix",                      "eda_fig4_scatter_matrix.png"),
    ("Fig 5: Outlier Detection (Z-Score)",         "eda_fig5_outlier_detection.png"),
    ("Fig 6: Credit Stress by Rate Regime",        "eda_fig6_regime_boxplots.png"),
    ("Fig 7: State Unemployment Distribution",     "eda_fig7_state_distribution.png"),
]

eda_html_blocks = []
for title, fname in eda_figures:
    fpath = EDA_DIR / fname
    if fpath.exists():
        b64 = img_to_b64(fpath)
        eda_html_blocks.append(f"""
        <div class="eda-card">
            <h3>{title}</h3>
            <img src="data:image/png;base64,{b64}" alt="{title}" />
        </div>
        """)
    else:
        eda_html_blocks.append(f"""
        <div class="eda-card missing">
            <h3>{title}</h3>
            <p>⚠ Image not found: {fname}<br>Run <code>python viz/eda.py</code> first.</p>
        </div>
        """)

# ── Load EDA summary text ──────────────────────────────────────────────────────
summary_path = EDA_DIR / "eda_summary.txt"
summary_text = summary_path.read_text() if summary_path.exists() else "Run eda.py to generate summary."

# ── Extract Bokeh visualizations ───────────────────────────────────────────────
bokeh_files = {
    "viz1": VIZ_DIR / "viz1_credit_stress_timeseries.html",
    "viz2": VIZ_DIR / "viz2_state_unemployment_map.html",
    "viz3": VIZ_DIR / "viz3_macro_scatter.html",
}

# Read full Bokeh HTML content for iframe embedding
def read_bokeh_html(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"<p>⚠ Not found: {path.name}. Run the viz script first.</p>"

# We'll embed Bokeh vizzes as srcdoc iframes to keep full interactivity
viz1_html = read_bokeh_html(bokeh_files["viz1"])
viz2_html = read_bokeh_html(bokeh_files["viz2"])
viz3_html = read_bokeh_html(bokeh_files["viz3"])

# Escape for srcdoc attribute
def escape_srcdoc(html: str) -> str:
    return html.replace("&", "&amp;").replace('"', "&quot;")

viz1_srcdoc = escape_srcdoc(viz1_html)
viz2_srcdoc = escape_srcdoc(viz2_html)
viz3_srcdoc = escape_srcdoc(viz3_html)

# ── Build full HTML ────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Consumer Credit Risk Analytics Dashboard</title>
    <style>
        /* ── Base ── */
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background: #F0F2F5;
            color: #1A1A2E;
            line-height: 1.5;
        }}

        /* ── Header ── */
        .header {{
            background: linear-gradient(135deg, #1A1A2E 0%, #16213E 50%, #0F3460 100%);
            color: white;
            padding: 36px 48px 28px;
        }}
        .header h1 {{
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.5px;
            margin-bottom: 6px;
        }}
        .header .subtitle {{
            font-size: 13px;
            color: rgba(255,255,255,0.65);
            font-weight: 400;
        }}
        .header .meta {{
            display: flex;
            gap: 24px;
            margin-top: 18px;
            flex-wrap: wrap;
        }}
        .badge {{
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 20px;
            padding: 4px 12px;
            font-size: 11px;
            color: rgba(255,255,255,0.85);
        }}

        /* ── Nav tabs ── */
        .nav {{
            background: #FFFFFF;
            border-bottom: 2px solid #E2E8F0;
            padding: 0 48px;
            display: flex;
            gap: 0;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }}
        .nav-tab {{
            padding: 14px 22px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            color: #64748B;
            transition: all 0.2s;
            white-space: nowrap;
        }}
        .nav-tab:hover {{ color: #0F3460; }}
        .nav-tab.active {{
            color: #0F3460;
            border-bottom-color: #0F3460;
            font-weight: 600;
        }}

        /* ── Main content ── */
        .content {{ padding: 32px 48px 60px; max-width: 1300px; margin: 0 auto; }}

        /* ── Section ── */
        .section {{ display: none; }}
        .section.active {{ display: block; }}

        .section-title {{
            font-size: 18px;
            font-weight: 700;
            color: #1A1A2E;
            margin-bottom: 6px;
        }}
        .section-desc {{
            font-size: 13px;
            color: #64748B;
            margin-bottom: 24px;
            max-width: 800px;
            line-height: 1.6;
        }}

        /* ── KPI cards ── */
        .kpi-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .kpi-card {{
            background: white;
            border-radius: 10px;
            padding: 18px 20px;
            border-left: 4px solid;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }}
        .kpi-card .kpi-label {{ font-size: 11px; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; }}
        .kpi-card .kpi-value {{ font-size: 24px; font-weight: 700; margin: 4px 0 2px; }}
        .kpi-card .kpi-note  {{ font-size: 11px; color: #94A3B8; }}

        /* ── Bokeh iframe ── */
        .bokeh-wrapper {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 28px;
            box-shadow: 0 1px 6px rgba(0,0,0,0.07);
        }}
        .bokeh-wrapper h3 {{
            font-size: 14px;
            font-weight: 600;
            color: #334155;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #F1F5F9;
        }}
        .bokeh-wrapper .viz-desc {{
            font-size: 12px;
            color: #64748B;
            margin-bottom: 12px;
            font-style: italic;
        }}
        iframe.bokeh-frame {{
            width: 100%;
            border: none;
            border-radius: 6px;
            background: white;
        }}

        /* ── EDA grid ── */
        .eda-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(580px, 1fr));
            gap: 20px;
        }}
        .eda-card {{
            background: white;
            border-radius: 12px;
            padding: 18px 20px;
            box-shadow: 0 1px 6px rgba(0,0,0,0.07);
        }}
        .eda-card h3 {{
            font-size: 13px;
            font-weight: 600;
            color: #334155;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #F1F5F9;
        }}
        .eda-card img {{
            width: 100%;
            height: auto;
            border-radius: 4px;
        }}
        .eda-card.missing {{
            border: 2px dashed #E2E8F0;
            color: #94A3B8;
            font-size: 13px;
        }}

        /* ── Summary text ── */
        .summary-box {{
            background: #1A1A2E;
            color: #A8D8A8;
            font-family: "SF Mono", "Fira Code", monospace;
            font-size: 11.5px;
            padding: 24px 28px;
            border-radius: 10px;
            white-space: pre-wrap;
            line-height: 1.7;
            overflow-x: auto;
            margin-top: 24px;
        }}

        /* ── About section ── */
        .about-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .about-card {{
            background: white;
            border-radius: 12px;
            padding: 22px 24px;
            box-shadow: 0 1px 6px rgba(0,0,0,0.07);
        }}
        .about-card h3 {{
            font-size: 14px;
            font-weight: 600;
            color: #0F3460;
            margin-bottom: 12px;
        }}
        .about-card ul {{ padding-left: 18px; }}
        .about-card li {{ font-size: 13px; color: #475569; margin-bottom: 6px; line-height: 1.5; }}
        .about-card p  {{ font-size: 13px; color: #475569; line-height: 1.6; }}

        .pipeline-flow {{
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 16px 20px;
            font-family: "SF Mono", monospace;
            font-size: 11.5px;
            color: #334155;
            line-height: 2;
            margin-top: 12px;
        }}
    </style>
</head>
<body>

<!-- ── Header ── -->
<div class="header">
    <h1>Consumer Credit Risk Analytics Dashboard</h1>
    <div class="subtitle">Macroeconomic stress monitoring for banking portfolio risk assessment</div>
    <div class="meta">
        <span class="badge">📊 FRED Federal Reserve API</span>
        <span class="badge">🏦 FDIC BankFind API</span>
        <span class="badge">📍 BLS / FRED State Data</span>
        <span class="badge">🗓 2014–2024 | 44 Quarters</span>
        <span class="badge">🔧 Apache Airflow · AWS S3 · Python · Bokeh · Matplotlib</span>
    </div>
</div>

<!-- ── Nav ── -->
<nav class="nav">
    <div class="nav-tab active" onclick="showSection('overview')">📈 Overview</div>
    <div class="nav-tab" onclick="showSection('viz1')">Time Series</div>
    <div class="nav-tab" onclick="showSection('viz2')">State Map</div>
    <div class="nav-tab" onclick="showSection('viz3')">Scatter Analysis</div>
    <div class="nav-tab" onclick="showSection('eda')">🔬 EDA</div>
    <div class="nav-tab" onclick="showSection('about')">ℹ About</div>
</nav>

<!-- ── Content ── -->
<div class="content">

    <!-- Overview -->
    <div class="section active" id="section-overview">
        <div class="section-title">Dashboard Overview</div>
        <div class="section-desc">
            This dashboard monitors U.S. consumer credit stress indicators from 2014–2024,
            combining Federal Reserve economic data, FDIC banking performance metrics, and
            state-level labor statistics. It is designed to support banking risk teams in
            identifying macroeconomic conditions that precede credit deterioration.
        </div>

        <!-- KPI Cards -->
        <div class="kpi-row">
            <div class="kpi-card" style="border-color: #E8474C;">
                <div class="kpi-label">Current Delinquency Rate</div>
                <div class="kpi-value" style="color:#E8474C;">3.2%</div>
                <div class="kpi-note">Q4 2024 · Up from 1.6% low (2022)</div>
            </div>
            <div class="kpi-card" style="border-color: #F4A225;">
                <div class="kpi-label">Credit Card Charge-Off Rate</div>
                <div class="kpi-value" style="color:#F4A225;">3.0%</div>
                <div class="kpi-note">Q4 2024 · Rising since 2022 lows</div>
            </div>
            <div class="kpi-card" style="border-color: #2166AC;">
                <div class="kpi-label">Federal Funds Rate</div>
                <div class="kpi-value" style="color:#2166AC;">4.3%</div>
                <div class="kpi-note">Q4 2024 · High regime (5%+ peak 2023)</div>
            </div>
            <div class="kpi-card" style="border-color: #4DAC26;">
                <div class="kpi-label">U.S. Unemployment Rate</div>
                <div class="kpi-value" style="color:#4DAC26;">4.2%</div>
                <div class="kpi-note">Q4 2024 · Near full employment</div>
            </div>
            <div class="kpi-card" style="border-color: #7B2D8B;">
                <div class="kpi-label">States Above 4% Unemployment</div>
                <div class="kpi-value" style="color:#7B2D8B;">22</div>
                <div class="kpi-note">Dec 2024 · Incl. CA, MI, IL, NJ</div>
            </div>
            <div class="kpi-card" style="border-color: #888888;">
                <div class="kpi-label">Quarters Analyzed</div>
                <div class="kpi-value" style="color:#555;">44</div>
                <div class="kpi-note">2014 Q1 — 2024 Q4</div>
            </div>
        </div>

        <!-- Key insight -->
        <div class="bokeh-wrapper">
            <h3>📌 Key Analytical Finding</h3>
            <p style="font-size:13.5px; color:#334155; line-height:1.7; max-width:860px;">
                Consumer loan delinquency rates exhibit a <strong>lagged response to interest rate cycles</strong>
                of approximately 2–4 quarters. The Federal Reserve's 2022 rate hike cycle — the fastest in 40 years —
                drove delinquency from a historic low of <strong>1.6%</strong> in 2022 Q1 to <strong>3.2%</strong>
                by 2024 Q3, nearly doubling. This lag relationship is the core signal for banking
                risk teams monitoring portfolio health under tightening monetary conditions.
                <br><br>
                State-level unemployment shows a <strong>3.7% national spread</strong> (1.9% South Dakota
                to 5.6% DC), with 22 states above the ~4% full-employment threshold — suggesting
                geographic concentration risk in bank loan portfolios exposed to those markets.
            </p>
        </div>
    </div>

    <!-- Viz 1 -->
    <div class="section" id="section-viz1">
        <div class="section-title">Credit Stress Time Series (2014–2024)</div>
        <div class="section-desc">
            Interactive time series showing consumer loan delinquency rate, credit card charge-off rate,
            and the federal funds rate from 2014–2024. Use the date range slider to zoom into specific periods.
            Toggle individual series on/off using the checkboxes. Key events (COVID-19, Fed rate hike cycle,
            SVB collapse) are annotated with dashed reference lines.
        </div>
        <div class="bokeh-wrapper">
            <h3>Viz 1 — U.S. Consumer Credit Stress Indicators</h3>
            <div class="viz-desc">Drag the slider to filter date range · Click legend items to toggle series · Hover for exact values</div>
            <iframe class="bokeh-frame" srcdoc="{viz1_srcdoc}" height="560"></iframe>
        </div>
    </div>

    <!-- Viz 2 -->
    <div class="section" id="section-viz2">
        <div class="section-title">State-Level Unemployment Map — December 2024</div>
        <div class="section-desc">
            Geographic view of unemployment rates across all 50 states and DC as of December 2024.
            Green indicates low unemployment; red indicates high. Hover over any state to see its
            exact rate and national rank. This view supports geographic risk concentration analysis
            for bank loan portfolios.
        </div>
        <div class="bokeh-wrapper">
            <h3>Viz 2 — State Unemployment Choropleth (Source: FRED API)</h3>
            <div class="viz-desc">Hover over states for rate and rank · Scroll to zoom · Drag to pan</div>
            <iframe class="bokeh-frame" srcdoc="{viz2_srcdoc}" height="560"></iframe>
        </div>
    </div>

    <!-- Viz 3 -->
    <div class="section" id="section-viz3">
        <div class="section-title">Macro Correlation Scatter Analysis</div>
        <div class="section-desc">
            Each bubble represents one quarter from 2014–2024. X-axis shows the unemployment rate,
            Y-axis shows consumer loan delinquency. Bubble size reflects total consumer credit outstanding
            (larger = more credit in the system). Color indicates the prevailing interest rate regime.
            Use the dropdown to filter by regime. The dashed vertical line marks the ~4% full-employment threshold.
        </div>
        <div class="bokeh-wrapper">
            <h3>Viz 3 — Unemployment vs. Delinquency by Rate Regime</h3>
            <div class="viz-desc">Filter by rate regime using dropdown · Hover bubbles for quarter details · Bubble size = consumer credit outstanding</div>
            <iframe class="bokeh-frame" srcdoc="{viz3_srcdoc}" height="600"></iframe>
        </div>
    </div>

    <!-- EDA -->
    <div class="section" id="section-eda">
        <div class="section-title">Exploratory Data Analysis</div>
        <div class="section-desc">
            Pre-visualization statistical analysis performed on the gold-layer data before building
            interactive dashboards. EDA validates data quality, identifies distributions and outliers,
            tests correlations, and confirms that the story the visualizations tell is statistically grounded.
        </div>
        <div class="eda-grid">
            {''.join(eda_html_blocks)}
        </div>

    </div>

    <!-- About -->
    <div class="section" id="section-about">
        <div class="section-title">About This Dashboard</div>
        <div class="section-desc">Pipeline architecture, data sources, and methodology documentation.</div>
        <div class="about-grid">
            <div class="about-card">
                <h3>🔧 Pipeline Architecture</h3>
                <div class="pipeline-flow">FRED API ──┐
FDIC API ──┼──► Airflow DAG ──► S3 Bronze
BLS/FRED  ──┘         │
                       ▼
              S3 Silver (cleaned)
              Python transforms
                       │
                       ▼
              S3 Gold (marts)
              Joined + aggregated
                  │          │
                  ▼          ▼
               Bokeh      Tableau
            (Viz 1+2+3)  (Scatter)</div>
            </div>
            <div class="about-card">
                <h3>📊 Data Sources</h3>
                <ul>
                    <li><strong>FRED (Federal Reserve)</strong> — Consumer loan delinquency rate (DRCCLACBS), credit card charge-off rate (CORCACBS), federal funds rate (FEDFUNDS), unemployment (UNRATE), CPI (CPIAUCSL), consumer credit outstanding (TOTALSL)</li>
                    <li><strong>FDIC BankFind API</strong> — Aggregate U.S. banking financials: total assets, deposits, net loans, net charge-offs (quarterly)</li>
                    <li><strong>FRED State Series</strong> — State-level unemployment rates for all 50 states + DC (December 2024)</li>
                </ul>
            </div>
            <div class="about-card">
                <h3>🧹 Data Cleaning Methodology</h3>
                <ul>
                    <li>Duplicate removal by date key before any transformation</li>
                    <li>Forward-fill (limit 2 periods) for small gaps in quarterly series</li>
                    <li>Z-score outlier flagging at |z| > 3.5 threshold</li>
                    <li>Numeric coercion with error handling for FRED "." missing values</li>
                    <li>Monthly FRED data resampled to quarterly (QE) via mean aggregation</li>
                    <li>Data quality gate validates all bronze files before transforms run</li>
                </ul>
            </div>
            <div class="about-card">
                <h3>🛠 Technology Stack</h3>
                <ul>
                    <li><strong>Orchestration:</strong> Apache Airflow DAG (8 tasks)</li>
                    <li><strong>Storage:</strong> AWS S3 medallion architecture (bronze/silver/gold)</li>
                    <li><strong>Processing:</strong> Python 3.12, pandas 2.0, scipy, numpy</li>
                    <li><strong>EDA:</strong> Matplotlib (7 analytical figures)</li>
                    <li><strong>Interactive Viz:</strong> Bokeh 3.x (3 dashboards)</li>
                    <li><strong>BI Layer:</strong> Tableau (scatter mart)</li>
                    <li><strong>Author:</strong> Gretchen Kolthoff</li>

                </ul>
            </div>
        </div>
    </div>

</div>

<script>
function showSection(name) {{
    // Hide all sections
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));

    // Show selected
    document.getElementById('section-' + name).classList.add('active');

    // Activate tab
    const tabs = document.querySelectorAll('.nav-tab');
    const names = ['overview', 'viz1', 'viz2', 'viz3', 'eda', 'about'];
    const idx = names.indexOf(name);
    if (idx >= 0) tabs[idx].classList.add('active');
}}
</script>

</body>
</html>"""

# ── Save ───────────────────────────────────────────────────────────────────────
out_path = VIZ_DIR / "dashboard.html"
out_path.write_text(html, encoding="utf-8")
print(f"Dashboard saved: {out_path}")
print(f"File size: {out_path.stat().st_size / 1024 / 1024:.1f} MB")
