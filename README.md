#                                                   Consumer Credit Risk Analytics Dashboard

A multi-source data pipeline and interactive analytics dashboard tracking U.S. consumer credit stress indicators from 2014–2024. Built with Apache Airflow, Python, Bokeh, Matplotlib, and Tableau.
<img width="899" height="512" alt="image" src="https://github.com/user-attachments/assets/9e4a96ab-6054-4380-a42f-dfb54295dc2b" />



## The Hypothesis

**Interest rate regime is a stronger predictor of consumer credit stress than unemployment rate.**

This challenges the conventional assumption that job loss is the primary driver of loan delinquency. The data shows the federal funds rate correlates with consumer loan delinquency at **r = 0.80**, while unemployment correlates at only **r = -0.28**. ANOVA testing confirms delinquency levels differ significantly across rate regimes (F = 28.50, p < 0.001).

The practical implication: rising interest rates create a **2–4 quarter lag** before delinquency peaks — giving risk teams an early warning window to adjust underwriting standards, increase loan loss reserves, or tighten credit thresholds before losses materialize.


## Dashboard Purpose

This dashboard is designed for financial analysts, risk managers, and business stakeholders who need to understand not just whether credit risk is rising, but **why** — and what macroeconomic signals to watch for next.

Credit risk sits at the convergence of macroeconomic forecasting, individual borrower behavior, fraud detection, and regulatory oversight. The same analytical methods used here apply across industries: supply chain demand forecasting, organizational budget risk, and procurement analytics all follow the same logic of connecting leading indicators to lagging outcomes.



## Visualizations

| Visualization | Tool | What It Shows |
|---|---|---|
| [Credit Stress Time Series](viz/viz1_credit_stress_timeseries.html) | Bokeh | Delinquency, charge-off, and fed funds rate 2014–2024 with event annotations |
| [State Unemployment Map](viz/viz2_state_unemployment_map.html) | Bokeh | Geographic unemployment distribution across all 50 states + DC |
| [Macro Correlation Scatter](viz/viz3_macro_scatter.html) | Bokeh | Unemployment vs. delinquency by interest rate regime |
| [Full Dashboard](viz/dashboard.html) | HTML | All visualizations + EDA in a single tabbed interface |
| Tableau Scatter | Tableau Public | Interactive rate regime filter and date range slider |

### How to Interact

**Time Series (Viz 1)**
- Drag the **Date Range slider** to zoom into specific periods — try isolating 2022–2024 to see the rate hike effect
- Use **checkboxes** to show/hide individual lines
- **Hover** over any point for exact quarterly values
- Three dashed lines mark COVID-19 onset, the 2022 Fed rate hike cycle, and SVB collapse

**State Map (Viz 2)**
- **Hover** over any state to see unemployment rate and national rank
- Green = low unemployment, Red = high unemployment
- Scroll to zoom, drag to pan

**Scatter Analysis (Viz 3 — Tableau)**
- Use **Rate Regime checkboxes** to isolate specific monetary policy environments
- Use the **Date range slider** to filter by time period
- **Hover** over bubbles for quarter, unemployment rate, delinquency rate, and fed funds rate
- Bubble size = total consumer credit outstanding
- Dashed vertical line at 4.0% = full employment threshold

**Full Dashboard**
- Open `viz/dashboard.html` in any modern browser — no server or login required
- Use the **tab navigation** to move between Overview, Time Series, State Map, Scatter Analysis, EDA, and About



## Pipeline Architecture


FRED API ──┐
FDIC API ──┼──► Apache Airflow DAG ──► S3 Bronze (raw)
BLS/FRED  ──┘           │
                         ▼
                  S3 Silver (cleaned)
                  Python transforms
                         │
                         ▼
                  S3 Gold (analytics marts)
                  Joined + aggregated
                    │              │
                    ▼              ▼
                 Bokeh          Tableau
              (Viz 1+2+3)    (Scatter mart)


Data follows a **medallion architecture** (bronze → silver → gold):
- **Bronze** — raw JSON/CSV from APIs
- **Silver** — cleaned, validated, transformed
- **Gold** — joined analytics-ready datasets for visualization



## Data Sources

| Source | Data | API |
|---|---|---|
| [FRED (Federal Reserve)](https://fred.stlouisfed.org) | Delinquency rates, charge-off rates, fed funds rate, unemployment, CPI, consumer credit outstanding | Free API key required |
| [FDIC BankFind](https://banks.data.fdic.gov) | Aggregate banking financials: assets, deposits, net loans, charge-offs | No key required |
| [FRED State Series](https://fred.stlouisfed.org) | State-level unemployment rates for all 50 states + DC | Same FRED key |



## Setup & Running the Pipeline

```bash
# 1. Clone the repo
git clone https://github.com/GretchenK20/credit-risk-analytics-pipeline.git
cd credit-risk-analytics-pipeline

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your FRED API key (free at fred.stlouisfed.org)
export FRED_API_KEY="your_key_here"

# 4. Run the full pipeline
python run_pipeline.py

# 5. Generate state choropleth data
python tasks/pull_fred_states.py

# 6. Build visualizations
python viz/viz1_timeseries.py
python viz/viz2_choropleth.py
python viz/viz3_scatter.py
python viz/eda.py
python viz/build_dashboard.py

# 7. Open the dashboard
open viz/dashboard.html
```

The gold layer CSVs and HTML files are pre-built in this repo — you can open `viz/dashboard.html` directly without running the pipeline.



## EDA Findings

Seven exploratory figures were generated before building visualizations:

- **Distributions** — Delinquency and charge-off rates are approximately normal; fed funds rate is right-skewed (prolonged near-zero period 2014–2021)
- **Correlation Matrix** — Fed funds rate → delinquency: r=0.80; Unemployment → delinquency: r=-0.28
- **Time Series + Rolling Stats** — Delinquency hit historic low of 1.53% in 2021 Q3, rose to 3.22% by 2024 Q3
- **Outlier Detection** — Only COVID-19 Q2 2020 unemployment spike exceeded 2.5σ threshold
- **ANOVA by Rate Regime** — F=28.50, p<0.001 confirms rate regime significantly predicts delinquency level



## Tech Stack

| Component | Technology |
|---|---|
| Orchestration | Apache Airflow 3.3.1 (DAG: `dags/credit_risk_dag.py`) |
| Storage | AWS S3 medallion architecture (bronze/silver/gold) |
| Processing | Python 3.12, pandas 2.0+, scipy, numpy |
| EDA | Matplotlib (7 analytical figures) |
| Interactive Viz | Bokeh 3.x (3 dashboards) |
| BI Layer | Tableau Public |
| Dependency Mgmt | python-dotenv, requirements.txt |



## Author

**Gretchen Kolthoff **  
