"""
Task: pull_fdic
Layer: Bronze
Pulls aggregate U.S. banking performance data from FDIC BankFind API.
No API key required. Saves to local bronze/ and S3 bronze/.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd
import requests
from botocore.exceptions import NoCredentialsError, ClientError

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    FDIC_BASE_URL, FDIC_FIELDS, FDIC_START_DATE, FDIC_END_DATE,
    BRONZE_DIR, S3_BUCKET, S3_BRONZE_PREFIX, AWS_REGION,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def fetch_fdic_history(limit: int = 10000) -> pd.DataFrame:
    """
    Fetch aggregate U.S. banking statistics from FDIC BankFind /history endpoint.
    Returns quarterly aggregate data across all FDIC-insured institutions.
    """
    endpoint = f"{FDIC_BASE_URL}/history"
    fields_str = ",".join(FDIC_FIELDS)

    params = {
        "filters":  f"REPDTE:[{FDIC_START_DATE} TO {FDIC_END_DATE}]",
        "fields":   fields_str,
        "limit":    limit,
        "offset":   0,
        "sort_by":  "REPDTE",
        "sort_order": "ASC",
        "output":   "json",
    }

    log.info(f"Fetching FDIC history: {endpoint}")
    resp = requests.get(endpoint, params=params, timeout=60)

    # FDIC API returns 200 even for bad requests sometimes — check content
    if resp.status_code != 200:
        log.warning(f"FDIC history returned {resp.status_code}, trying /institutions summary")
        return fetch_fdic_institutions_summary()

    try:
        data = resp.json()
        if "data" in data and len(data["data"]) > 0:
            records = [item.get("data", item) for item in data["data"]]
            df = pd.DataFrame(records)
            log.info(f"FDIC history: {len(df)} records")
            return df
        else:
            log.warning("FDIC history returned empty data, falling back to institutions")
            return fetch_fdic_institutions_summary()
    except Exception as e:
        log.warning(f"FDIC history parse error: {e}, falling back")
        return fetch_fdic_institutions_summary()


def fetch_fdic_institutions_summary() -> pd.DataFrame:
    """
    Fallback: fetch aggregate financial data from FDIC /financials endpoint.
    Aggregates by report date across all institutions.
    """
    endpoint = f"{FDIC_BASE_URL}/financials"

    # Core financial fields available in /financials
    fields = [
        "REPDTE", "ASSET", "DEP", "LNLSNET",
        "NETINC", "INTINC", "NETCHARGE", "LNLSDEPR", "LNLSDEPP"
    ]

    all_records = []
    offset = 0
    limit  = 10000

    while True:
        params = {
            "filters":    f"REPDTE:[{FDIC_START_DATE} TO {FDIC_END_DATE}]",
            "fields":     ",".join(fields),
            "limit":      limit,
            "offset":     offset,
            "sort_by":    "REPDTE",
            "sort_order": "ASC",
            "output":     "json",
            "agg_by":     "REPDTE",
            "agg_sum_fields": ",".join([f for f in fields if f != "REPDTE"]),
            "agg_limit":  200,
        }

        resp = requests.get(endpoint, params=params, timeout=60)
        if resp.status_code != 200:
            log.error(f"FDIC financials returned {resp.status_code}")
            break

        try:
            data = resp.json()
        except Exception:
            break

        records = data.get("data", [])
        if not records:
            break

        for item in records:
            all_records.append(item.get("data", item))

        total = data.get("meta", {}).get("total", 0)
        offset += limit
        if offset >= total or len(records) < limit:
            break

    if all_records:
        df = pd.DataFrame(all_records)
        log.info(f"FDIC financials aggregated: {len(df)} date periods")
        return df

    # Final fallback: return synthetic structure so pipeline doesn't break
    log.warning("FDIC API returned no usable data — using minimal stub")
    return pd.DataFrame()


def upload_to_s3(local_path: Path, s3_key: str) -> bool:
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.upload_file(str(local_path), S3_BUCKET, s3_key)
        log.info(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")
        return True
    except (NoCredentialsError, ClientError) as e:
        log.warning(f"S3 upload skipped: {e}")
        return False


def run():
    log.info("=== pull_fdic: START ===")
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    df = fetch_fdic_history()

    if df.empty:
        log.warning("FDIC returned no data — writing empty bronze file")
        df = pd.DataFrame(columns=FDIC_FIELDS)

    # Standardize date column
    if "REPDTE" in df.columns:
        df["REPDTE"] = pd.to_datetime(df["REPDTE"], format="%Y%m%d", errors="coerce")
        df = df.rename(columns={"REPDTE": "date"})

    # Numeric coercion
    for col in df.columns:
        if col not in ["date", "source", "fetched_at"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["source"]     = "FDIC_BankFind"
    df["fetched_at"] = run_ts

    # Save locally
    out_path    = BRONZE_DIR / f"fdic_bronze_{run_ts}.csv"
    latest_path = BRONZE_DIR / "fdic_bronze_latest.csv"
    df.to_csv(out_path, index=False)
    df.to_csv(latest_path, index=False)
    log.info(f"Bronze CSV saved: {out_path} ({len(df)} rows)")

    # Upload to S3
    upload_to_s3(out_path,    f"{S3_BRONZE_PREFIX}/fdic/fdic_bronze_{run_ts}.csv")
    upload_to_s3(latest_path, f"{S3_BRONZE_PREFIX}/fdic/fdic_bronze_latest.csv")

    log.info(f"=== pull_fdic: COMPLETE — {len(df)} rows ===")
    return str(out_path)


if __name__ == "__main__":
    run()
