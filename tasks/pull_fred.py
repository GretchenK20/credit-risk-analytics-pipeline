"""
Task: pull_fred
Layer: Bronze
Pulls all FRED series defined in config, saves raw JSON + CSV to S3 bronze/
and local bronze/ mirror.
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
    FRED_API_KEY, FRED_SERIES, FRED_START_DATE, FRED_END_DATE,
    BRONZE_DIR, S3_BUCKET, S3_BRONZE_PREFIX, AWS_REGION,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def fetch_series(series_id: str) -> pd.DataFrame:
    """Fetch a single FRED series and return as DataFrame."""
    params = {
        "series_id":        series_id,
        "observation_start": FRED_START_DATE,
        "observation_end":   FRED_END_DATE,
        "file_type":        "json",
        "api_key":          FRED_API_KEY,
    }
    resp = requests.get(FRED_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    observations = data.get("observations", [])
    if not observations:
        log.warning(f"No observations returned for {series_id}")
        return pd.DataFrame()

    df = pd.DataFrame(observations)[["date", "value"]]
    df.columns = ["date", series_id]
    df["date"] = pd.to_datetime(df["date"])
    # FRED uses "." for missing values
    df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
    return df


def upload_to_s3(local_path: Path, s3_key: str) -> bool:
    """Upload a file to S3. Returns True on success, False if no credentials."""
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.upload_file(str(local_path), S3_BUCKET, s3_key)
        log.info(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")
        return True
    except NoCredentialsError:
        log.warning("No AWS credentials found — skipping S3 upload, local only.")
        return False
    except ClientError as e:
        log.warning(f"S3 upload failed: {e} — local file retained.")
        return False


def run():
    """
    Main entry point for the pull_fred Airflow task.
    Pulls all series, saves individual raw JSONs + combined CSV to bronze layer.
    """
    log.info("=== pull_fred: START ===")
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    run_ts  = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    frames  = {}
    raw_dir = BRONZE_DIR / "fred_raw"
    raw_dir.mkdir(exist_ok=True)

    # Deduplicate series IDs (config may map multiple names to same series)
    unique_series = {v: k for k, v in FRED_SERIES.items()}

    for series_id, label in unique_series.items():
        log.info(f"Fetching FRED series: {series_id} ({label})")
        try:
            df = fetch_series(series_id)
            if df.empty:
                continue

            # Save raw JSON response locally
            raw_path = raw_dir / f"{series_id}_{run_ts}.json"
            resp_params = {
                "series_id": series_id,
                "start": FRED_START_DATE,
                "end":   FRED_END_DATE,
                "fetched_at": run_ts,
                "rows": len(df),
            }
            raw_path.write_text(json.dumps(resp_params, indent=2))

            frames[series_id] = df
            log.info(f"  → {len(df)} observations")

        except requests.RequestException as e:
            log.error(f"Failed to fetch {series_id}: {e}")
            continue

    if not frames:
        raise RuntimeError("No FRED data fetched — check API key and network.")

    # Merge all series on date
    combined = None
    for series_id, df in frames.items():
        if combined is None:
            combined = df
        else:
            combined = pd.merge(combined, df, on="date", how="outer")

    combined = combined.sort_values("date").reset_index(drop=True)

    # Rename columns to friendly names using reverse lookup
    id_to_label = {v: k for k, v in FRED_SERIES.items()}
    combined = combined.rename(columns=id_to_label)

    # Add metadata columns
    combined["source"]     = "FRED"
    combined["fetched_at"] = run_ts

    # Save combined bronze CSV locally
    out_path = BRONZE_DIR / f"fred_bronze_{run_ts}.csv"
    combined.to_csv(out_path, index=False)
    log.info(f"Bronze CSV saved: {out_path} ({len(combined)} rows, {len(combined.columns)} cols)")

    # Also save a stable "latest" copy for downstream tasks
    latest_path = BRONZE_DIR / "fred_bronze_latest.csv"
    combined.to_csv(latest_path, index=False)

    # Upload both to S3
    upload_to_s3(out_path,    f"{S3_BRONZE_PREFIX}/fred/fred_bronze_{run_ts}.csv")
    upload_to_s3(latest_path, f"{S3_BRONZE_PREFIX}/fred/fred_bronze_latest.csv")

    log.info(f"=== pull_fred: COMPLETE — {len(combined)} rows, {len(unique_series)} series ===")
    return str(out_path)


if __name__ == "__main__":
    run()
