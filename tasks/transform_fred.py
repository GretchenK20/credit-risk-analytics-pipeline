"""
Task: transform_fred
Layer: Bronze → Silver
Cleans FRED bronze data: handles nulls, outlier flagging,
interest rate regime classification, rolling stats.
Saves to silver/ locally and S3.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import boto3
import numpy as np
import pandas as pd
from botocore.exceptions import NoCredentialsError, ClientError
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BRONZE_DIR, SILVER_DIR, S3_BUCKET,
    S3_BRONZE_PREFIX, S3_SILVER_PREFIX, AWS_REGION,
    MAX_NULL_PCT, MIN_ROWS_FRED, ZSCORE_OUTLIER_FLAG,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def classify_rate_regime(fed_funds_rate: float) -> str:
    """Classify interest rate environment for Tableau scatter coloring."""
    if pd.isna(fed_funds_rate):
        return "Unknown"
    if fed_funds_rate < 1.0:
        return "Ultra-Low (<1%)"
    elif fed_funds_rate < 3.0:
        return "Low (1-3%)"
    elif fed_funds_rate < 5.0:
        return "Moderate (3-5%)"
    else:
        return "High (5%+)"


def flag_outliers(series: pd.Series, threshold: float = ZSCORE_OUTLIER_FLAG) -> pd.Series:
    """Return boolean Series: True where value is a statistical outlier."""
    z = np.abs(stats.zscore(series.dropna()))
    outlier_idx = series.dropna().index[z > threshold]
    flags = pd.Series(False, index=series.index)
    flags[outlier_idx] = True
    return flags


def validate_quality(df: pd.DataFrame, name: str) -> dict:
    """Run data quality checks, return report dict."""
    report = {"dataset": name, "rows": len(df), "issues": []}

    if len(df) < MIN_ROWS_FRED:
        report["issues"].append(f"Low row count: {len(df)} < {MIN_ROWS_FRED}")

    for col in df.columns:
        if col in ["date", "source", "fetched_at", "rate_regime"]:
            continue
        null_pct = df[col].isna().mean()
        if null_pct > MAX_NULL_PCT:
            report["issues"].append(f"{col}: {null_pct:.1%} nulls (threshold {MAX_NULL_PCT:.0%})")

    report["passed"] = len(report["issues"]) == 0
    return report


def run():
    log.info("=== transform_fred: START ===")
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # Load bronze
    bronze_path = BRONZE_DIR / "fred_bronze_latest.csv"
    if not bronze_path.exists():
        raise FileNotFoundError(f"Bronze file not found: {bronze_path}. Run pull_fred first.")

    df = pd.read_csv(bronze_path, parse_dates=["date"])
    log.info(f"Loaded bronze: {len(df)} rows, columns: {list(df.columns)}")

    # ── Cleaning ───────────────────────────────────────────────────────────────
    # Drop pure duplicates
    before = len(df)
    df = df.drop_duplicates(subset=["date"])
    log.info(f"Deduplication: {before - len(df)} rows removed")

    # Sort by date
    df = df.sort_values("date").reset_index(drop=True)

    # Forward-fill small gaps (≤2 periods) — common in quarterly FRED series
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    df[numeric_cols] = df[numeric_cols].ffill(limit=2)

    # ── Derived features ───────────────────────────────────────────────────────
    # Interest rate regime for Tableau coloring
    rate_col = "fed_funds_rate" if "fed_funds_rate" in df.columns else None
    if rate_col:
        df["rate_regime"] = df[rate_col].apply(classify_rate_regime)

    # 4-quarter rolling average for delinquency (smooths seasonality)
    for col in ["delinquency_all", "chargeoff_all"]:
        if col in df.columns:
            df[f"{col}_rolling4q"] = df[col].rolling(window=4, min_periods=2).mean()

    # YoY change in delinquency
    if "delinquency_all" in df.columns:
        df["delinquency_yoy_chg"] = df["delinquency_all"].pct_change(periods=4) * 100

    # Z-score for anomaly flagging
    for col in ["delinquency_all", "chargeoff_all", "fed_funds_rate"]:
        if col in df.columns:
            df[f"{col}_outlier_flag"] = flag_outliers(df[col])

    # Annotated events for Bokeh span lines
    df["annotation"] = ""
    df.loc[df["date"].between("2020-03-01", "2020-04-30"), "annotation"] = "COVID-19 Onset"
    df.loc[df["date"].between("2022-03-01", "2022-04-30"), "annotation"] = "Fed Rate Hike Cycle"
    df.loc[df["date"].between("2023-03-01", "2023-04-30"), "annotation"] = "SVB Collapse"

    # ── Quality validation ─────────────────────────────────────────────────────
    report = validate_quality(df, "fred_silver")
    if report["issues"]:
        for issue in report["issues"]:
            log.warning(f"DQ Issue: {issue}")
    else:
        log.info("Data quality: PASSED — no issues detected")

    # Add quality metadata
    df["dq_passed"]    = report["passed"]
    df["transform_ts"] = run_ts

    # ── Save ───────────────────────────────────────────────────────────────────
    out_path    = SILVER_DIR / f"fred_silver_{run_ts}.csv"
    latest_path = SILVER_DIR / "fred_silver_latest.csv"
    df.to_csv(out_path, index=False)
    df.to_csv(latest_path, index=False)
    log.info(f"Silver CSV saved: {out_path} ({len(df)} rows, {len(df.columns)} cols)")

    # Upload to S3
    for path, key in [
        (out_path,    f"{S3_SILVER_PREFIX}/fred/fred_silver_{run_ts}.csv"),
        (latest_path, f"{S3_SILVER_PREFIX}/fred/fred_silver_latest.csv"),
    ]:
        try:
            boto3.client("s3", region_name=AWS_REGION).upload_file(
                str(path), S3_BUCKET, key
            )
            log.info(f"Uploaded s3://{S3_BUCKET}/{key}")
        except (NoCredentialsError, ClientError) as e:
            log.warning(f"S3 upload skipped: {e}")

    log.info(f"=== transform_fred: COMPLETE ===")
    return str(out_path)


if __name__ == "__main__":
    run()
