"""
Task: transform_fdic_bls
Layer: Bronze → Silver
Cleans FDIC and BLS bronze data independently,
then saves each to silver layer.
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
    BRONZE_DIR, SILVER_DIR, S3_BUCKET,
    S3_SILVER_PREFIX, AWS_REGION,
    MAX_NULL_PCT, MIN_ROWS_FDIC, MIN_ROWS_BLS,
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


# ── FDIC Transform ─────────────────────────────────────────────────────────────

def transform_fdic(run_ts: str):
    log.info("--- transform_fdic ---")
    bronze_path = BRONZE_DIR / "fdic_bronze_latest.csv"
    if not bronze_path.exists():
        log.warning("FDIC bronze not found — skipping")
        return

    df = pd.read_csv(bronze_path, parse_dates=["date"], low_memory=False)
    log.info(f"FDIC bronze loaded: {len(df)} rows")

    if len(df) < MIN_ROWS_FDIC:
        log.warning(f"FDIC low row count: {len(df)}")

    # Numeric coercion
    skip_cols = {"date", "source", "fetched_at"}
    for col in df.columns:
        if col not in skip_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    # Derived: net charge-off rate = NETCHARGE / LNLSNET * 100
    if "NETCHARGE" in df.columns and "LNLSNET" in df.columns:
        df["chargeoff_rate_pct"] = (df["NETCHARGE"] / df["LNLSNET"].replace(0, np.nan)) * 100

    # Derived: past-due ratio = (30-89 day + 90+ day) / net loans
    if all(c in df.columns for c in ["LNLSDEPR", "LNLSDEPP", "LNLSNET"]):
        df["pastdue_rate_pct"] = (
            (df["LNLSDEPR"].fillna(0) + df["LNLSDEPP"].fillna(0))
            / df["LNLSNET"].replace(0, np.nan)
        ) * 100

    # Null report
    for col in df.select_dtypes(include=[np.number]).columns:
        null_pct = df[col].isna().mean()
        if null_pct > MAX_NULL_PCT:
            log.warning(f"FDIC DQ: {col} has {null_pct:.1%} nulls")

    df["transform_ts"] = run_ts

    out_path    = SILVER_DIR / f"fdic_silver_{run_ts}.csv"
    latest_path = SILVER_DIR / "fdic_silver_latest.csv"
    df.to_csv(out_path, index=False)
    df.to_csv(latest_path, index=False)
    log.info(f"FDIC silver saved: {out_path} ({len(df)} rows)")

    upload_to_s3(out_path,    f"{S3_SILVER_PREFIX}/fdic/fdic_silver_{run_ts}.csv")
    upload_to_s3(latest_path, f"{S3_SILVER_PREFIX}/fdic/fdic_silver_latest.csv")


# ── BLS Transform ──────────────────────────────────────────────────────────────

def transform_bls(run_ts: str):
    log.info("--- transform_bls ---")
    bronze_path = BRONZE_DIR / "bls_bronze_latest.csv"
    if not bronze_path.exists():
        log.warning("BLS bronze not found — skipping")
        return

    df = pd.read_csv(bronze_path)
    log.info(f"BLS bronze loaded: {len(df)} rows")

    # Keep annual averages only (month == 0) for choropleth simplicity
    if "month" in df.columns:
        df_annual = df[df["month"] == 0].copy()
        df_monthly = df[df["month"] > 0].copy()
        log.info(f"Annual averages: {len(df_annual)} | Monthly: {len(df_monthly)}")
    else:
        df_annual = df.copy()
        df_monthly = pd.DataFrame()

    # Clean annual
    df_annual = df_annual.dropna(subset=["unemployment_rate"])
    df_annual["unemployment_rate"] = pd.to_numeric(df_annual["unemployment_rate"], errors="coerce")
    df_annual = df_annual.drop_duplicates(subset=["state", "year"])

    # Validate state coverage
    n_states = df_annual["state"].nunique() if not df_annual.empty else 0
    if n_states < MIN_ROWS_BLS:
        log.warning(f"BLS low state coverage: {n_states} states")
    else:
        log.info(f"BLS state coverage: {n_states} states/DC")

    # Most recent year snapshot for choropleth
    if not df_annual.empty:
        latest_year = df_annual["year"].max()
        df_latest = df_annual[df_annual["year"] == latest_year].copy()
        df_latest["rank"] = df_latest["unemployment_rate"].rank(ascending=False).astype(int)

        latest_out    = SILVER_DIR / f"bls_state_latest_year_{run_ts}.csv"
        latest_stable = SILVER_DIR / "bls_state_latest_year.csv"
        df_latest.to_csv(latest_out, index=False)
        df_latest.to_csv(latest_stable, index=False)
        log.info(f"BLS latest-year choropleth saved: {latest_stable} ({len(df_latest)} states)")
        upload_to_s3(latest_out,    f"{S3_SILVER_PREFIX}/bls/bls_state_latest_year_{run_ts}.csv")
        upload_to_s3(latest_stable, f"{S3_SILVER_PREFIX}/bls/bls_state_latest_year.csv")

    # Full annual timeseries
    df_annual["transform_ts"] = run_ts
    out_path    = SILVER_DIR / f"bls_annual_silver_{run_ts}.csv"
    latest_path = SILVER_DIR / "bls_annual_silver_latest.csv"
    df_annual.to_csv(out_path, index=False)
    df_annual.to_csv(latest_path, index=False)
    log.info(f"BLS annual silver saved: {out_path} ({len(df_annual)} rows)")
    upload_to_s3(out_path,    f"{S3_SILVER_PREFIX}/bls/bls_annual_silver_{run_ts}.csv")
    upload_to_s3(latest_path, f"{S3_SILVER_PREFIX}/bls/bls_annual_silver_latest.csv")


def run():
    log.info("=== transform_fdic_bls: START ===")
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    transform_fdic(run_ts)
    transform_bls(run_ts)

    log.info("=== transform_fdic_bls: COMPLETE ===")


if __name__ == "__main__":
    run()
