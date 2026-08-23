"""
Supplemental task: pull_fred_states
Pulls state-level unemployment rates from FRED (one series per state).
FRED has clean state unemployment data under series pattern: [STATE]UR
e.g. MOURN = Missouri Unemployment Rate
Saves to data/gold/bls_choropleth_latest.csv for Bokeh Viz 2.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import FRED_API_KEY, GOLD_DIR, FRED_END_DATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# FRED state unemployment series IDs ([STATE ABBREV]UR)
STATE_SERIES = {
    "Alabama": "ALUR", "Alaska": "AKUR", "Arizona": "AZUR",
    "Arkansas": "ARUR", "California": "CAUR", "Colorado": "COUR",
    "Connecticut": "CTUR", "Delaware": "DEUR", "Florida": "FLUR",
    "Georgia": "GAUR", "Hawaii": "HIUR", "Idaho": "IDUR",
    "Illinois": "ILUR", "Indiana": "INUR", "Iowa": "IAUR",
    "Kansas": "KSUR", "Kentucky": "KYUR", "Louisiana": "LAUR",
    "Maine": "MEUR", "Maryland": "MDUR", "Massachusetts": "MAUR",
    "Michigan": "MIUR", "Minnesota": "MNUR", "Mississippi": "MSUR",
    "Missouri": "MOUR", "Montana": "MTUR", "Nebraska": "NEUR",
    "Nevada": "NVUR", "New Hampshire": "NHUR", "New Jersey": "NJUR",
    "New Mexico": "NMUR", "New York": "NYUR", "North Carolina": "NCUR",
    "North Dakota": "NDUR", "Ohio": "OHUR", "Oklahoma": "OKUR",
    "Oregon": "ORUR", "Pennsylvania": "PAUR", "Rhode Island": "RIUR",
    "South Carolina": "SCUR", "South Dakota": "SDUR", "Tennessee": "TNUR",
    "Texas": "TXUR", "Utah": "UTUR", "Vermont": "VTUR",
    "Virginia": "VAUR", "Washington": "WAUR", "West Virginia": "WVUR",
    "Wisconsin": "WIUR", "Wyoming": "WYUR", "District of Columbia": "DCUR",
}


def fetch_latest_state_unemployment() -> pd.DataFrame:
    """Fetch most recent unemployment rate for each state from FRED."""
    records = []

    for state, series_id in STATE_SERIES.items():
        params = {
            "series_id":         series_id,
            "observation_start": "2024-01-01",
            "observation_end":   FRED_END_DATE,
            "sort_order":        "desc",
            "limit":             1,
            "file_type":         "json",
            "api_key":           FRED_API_KEY,
        }
        try:
            resp = requests.get(FRED_BASE, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            obs  = data.get("observations", [])
            if obs:
                val = obs[0]["value"]
                dt  = obs[0]["date"]
                records.append({
                    "state":              state,
                    "series_id":          series_id,
                    "unemployment_rate":  float(val) if val != "." else None,
                    "date":               dt,
                })
                log.info(f"  {state}: {val}% ({dt})")
        except Exception as e:
            log.warning(f"  {state} ({series_id}) failed: {e}")

    return pd.DataFrame(records)


def run():
    log.info("=== pull_fred_states: START ===")
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    df = fetch_latest_state_unemployment()

    if df.empty:
        log.error("No state data returned — check FRED API key")
        return

    df = df.dropna(subset=["unemployment_rate"])
    df["rank"] = df["unemployment_rate"].rank(ascending=False).astype(int)
    df["year"] = pd.to_datetime(df["date"]).dt.year

    out = GOLD_DIR / "bls_choropleth_latest.csv"
    df.to_csv(out, index=False)
    log.info(f"State choropleth saved: {out} ({len(df)} states)")
    log.info(f"\n{df.sort_values('unemployment_rate', ascending=False).to_string(index=False)}")

    log.info("=== pull_fred_states: COMPLETE ===")
    return str(out)


if __name__ == "__main__":
    run()
