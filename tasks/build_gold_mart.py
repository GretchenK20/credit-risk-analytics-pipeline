"""
Task: build_gold_mart
Layer: Silver -> Gold
Joins FRED + FDIC silver layers into unified quarterly analytics mart.
Exports scatter mart (Tableau) and BLS choropleth mart (Bokeh).
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import boto3
import numpy as np
import pandas as pd
from botocore.exceptions import NoCredentialsError, ClientError

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    SILVER_DIR, GOLD_DIR, S3_BUCKET,
    S3_GOLD_PREFIX, AWS_REGION,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def upload_to_s3(local_path: Path, s3_key: str):
    try:
        boto3.client("s3", region_name=AWS_REGION).upload_file(
            str(local_path), S3_BUCKET, s3_key
        )
        log.info(f"Uploaded s3://{S3_BUCKET}/{s3_key}")
    except (NoCredentialsError, ClientError) as e:
        log.warning(f"S3 upload skipped: {e}")


def classify_rate_regime(r):
    if pd.isna(r):   return "Unknown"
    if r < 1.0:      return "Ultra-Low (<1%)"
    elif r < 3.0:    return "Low (1-3%)"
    elif r < 5.0:    return "Moderate (3-5%)"
    else:            return "High (5%+)"


def build_quarterly_mart(run_ts: str) -> pd.DataFrame:
    """Join FRED + FDIC silver into quarterly mart."""
    log.info("Building quarterly credit risk mart...")

    fred_path = SILVER_DIR / "fred_silver_latest.csv"
    if not fred_path.exists():
        raise FileNotFoundError("FRED silver not found — run transform_fred first.")

    fred = pd.read_csv(fred_path, parse_dates=["date"])
    log.info(f"FRED silver loaded: {len(fred)} rows, cols: {list(fred.columns)}")

    # Select only numeric columns for resample
    numeric_cols = fred.select_dtypes(include=[np.number]).columns.tolist()
    log.info(f"Numeric columns for resample: {numeric_cols}")

    # Resample monthly FRED -> quarterly (QE = quarter end, pandas 2.0+)
    fred_q = (
        fred.set_index("date")[numeric_cols]
        .resample("QE")
        .mean()
        .reset_index()
    )

    # Re-attach derived columns
    if "fed_funds_rate" in fred_q.columns:
        fred_q["rate_regime"] = fred_q["fed_funds_rate"].apply(classify_rate_regime)

    # Annotations
    fred_q["annotation"] = ""
    fred_q.loc[fred_q["date"].between("2020-01-01", "2020-06-30"), "annotation"] = "COVID-19 Onset"
    fred_q.loc[fred_q["date"].between("2022-01-01", "2022-06-30"), "annotation"] = "Fed Rate Hike Cycle"
    fred_q.loc[fred_q["date"].between("2023-01-01", "2023-06-30"), "annotation"] = "SVB Collapse"

    fred_q["source"]  = "FRED"
    fred_q["mart_ts"] = run_ts

    log.info(f"FRED quarterly mart: {len(fred_q)} quarters, cols: {list(fred_q.columns)}")

    # Merge FDIC if available
    fdic_path = SILVER_DIR / "fdic_silver_latest.csv"
    if fdic_path.exists():
        fdic = pd.read_csv(fdic_path, parse_dates=["date"])
        if not fdic.empty and "date" in fdic.columns:
            fdic_numeric = fdic.set_index("date").select_dtypes(include=[np.number])
            fdic_q = fdic_numeric.resample("QE").mean().reset_index()
            fdic_q.columns = (
                ["date"] + [f"fdic_{c}" for c in fdic_q.columns if c != "date"]
            )
            mart = pd.merge(fred_q, fdic_q, on="date", how="left")
            log.info(f"Merged with FDIC: {len(mart)} rows")
        else:
            mart = fred_q.copy()
    else:
        mart = fred_q.copy()

    return mart


def build_scatter_mart(quarterly_mart: pd.DataFrame, run_ts: str) -> pd.DataFrame:
    """
    Tableau scatter mart.
    X=unemployment_rate, Y=delinquency_all, Color=rate_regime,
    Size=consumer_credit_outstanding.
    Uses whatever columns are actually present.
    """
    log.info("Building scatter mart for Tableau...")
    log.info(f"Available columns: {list(quarterly_mart.columns)}")

    wanted = [
        "date", "unemployment_rate", "delinquency_all",
        "rate_regime", "consumer_credit_outstanding",
        "fed_funds_rate", "chargeoff_all", "annotation",
    ]
    available = [c for c in wanted if c in quarterly_mart.columns]
    log.info(f"Scatter mart using columns: {available}")

    scatter = quarterly_mart[available].copy()

    # Require at minimum unemployment_rate; delinquency optional
    dropna_on = [c for c in ["unemployment_rate"] if c in scatter.columns]
    if dropna_on:
        scatter = scatter.dropna(subset=dropna_on)

    # Quarter label for Tableau tooltip - pandas 2.0 safe
    scatter["quarter_label"] = (
        scatter["date"].dt.year.astype(str) + " Q" +
        scatter["date"].dt.quarter.astype(str)
    )
    scatter["mart_ts"] = run_ts

    log.info(f"Scatter mart: {len(scatter)} rows")
    return scatter


def run():
    log.info("=== build_gold_mart: START ===")
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # Quarterly mart
    quarterly = build_quarterly_mart(run_ts)
    q_out    = GOLD_DIR / f"quarterly_mart_{run_ts}.csv"
    q_latest = GOLD_DIR / "quarterly_mart_latest.csv"
    quarterly.to_csv(q_out, index=False)
    quarterly.to_csv(q_latest, index=False)
    log.info(f"Quarterly mart saved: {q_latest} ({len(quarterly)} rows)")
    upload_to_s3(q_out,    f"{S3_GOLD_PREFIX}/quarterly_mart_{run_ts}.csv")
    upload_to_s3(q_latest, f"{S3_GOLD_PREFIX}/quarterly_mart_latest.csv")

    # Scatter mart
    scatter  = build_scatter_mart(quarterly, run_ts)
    s_out    = GOLD_DIR / f"scatter_mart_{run_ts}.csv"
    s_latest = GOLD_DIR / "scatter_mart_latest.csv"
    scatter.to_csv(s_out, index=False)
    scatter.to_csv(s_latest, index=False)
    log.info(f"Scatter mart saved: {s_latest} ({len(scatter)} rows)")
    upload_to_s3(s_out,    f"{S3_GOLD_PREFIX}/scatter_mart_{run_ts}.csv")
    upload_to_s3(s_latest, f"{S3_GOLD_PREFIX}/scatter_mart_latest.csv")

    # BLS choropleth
    bls_path = SILVER_DIR / "bls_state_latest_year.csv"
    if bls_path.exists():
        bls      = pd.read_csv(bls_path)
        bls_out  = GOLD_DIR / f"bls_choropleth_{run_ts}.csv"
        bls_lat  = GOLD_DIR / "bls_choropleth_latest.csv"
        bls.to_csv(bls_out, index=False)
        bls.to_csv(bls_lat, index=False)
        log.info(f"BLS choropleth saved: {bls_lat} ({len(bls)} states)")
        upload_to_s3(bls_out, f"{S3_GOLD_PREFIX}/bls_choropleth_{run_ts}.csv")
        upload_to_s3(bls_lat, f"{S3_GOLD_PREFIX}/bls_choropleth_latest.csv")
    else:
        log.warning("BLS silver not found — choropleth skipped")

    log.info("=== build_gold_mart: COMPLETE ===")
    return str(q_latest)


if __name__ == "__main__":
    run()
