"""
Task: pull_bls
Layer: Bronze
Pulls state-level unemployment rates from BLS public API.
Batches requests (max 50 series per call per BLS limits).
Saves to local bronze/ and S3 bronze/.
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd
import requests
from botocore.exceptions import NoCredentialsError, ClientError

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BLS_API_KEY, BLS_BASE_URL, BLS_STATE_SERIES,
    BLS_START_YEAR, BLS_END_YEAR,
    BRONZE_DIR, S3_BUCKET, S3_BRONZE_PREFIX, AWS_REGION,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# BLS allows 50 series per request (25 without registration)
BATCH_SIZE = 25


def fetch_bls_batch(series_ids: list, state_names: list) -> pd.DataFrame:
    """Fetch a batch of BLS series IDs and return long-format DataFrame."""
    payload = {
        "seriesid":  series_ids,
        "startyear": BLS_START_YEAR,
        "endyear":   BLS_END_YEAR,
    }
    if BLS_API_KEY:
        payload["registrationkey"] = BLS_API_KEY

    resp = requests.post(
        BLS_BASE_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "REQUEST_SUCCEEDED":
        log.warning(f"BLS batch status: {data.get('status')} | {data.get('message', '')}")
        return pd.DataFrame()

    records = []
    series_to_state = dict(zip(series_ids, state_names))

    for series in data.get("Results", {}).get("series", []):
        sid   = series["seriesID"]
        state = series_to_state.get(sid, sid)

        for obs in series.get("data", []):
            try:
                # BLS annual data has period "M13" = annual average
                # Monthly has M01-M12
                period = obs.get("period", "")
                if period == "M13":
                    month = 0   # annual average marker
                elif period.startswith("M"):
                    month = int(period[1:])
                else:
                    continue

                records.append({
                    "state":         state,
                    "series_id":     sid,
                    "year":          int(obs["year"]),
                    "month":         month,
                    "period_name":   obs.get("periodName", ""),
                    "unemployment_rate": float(obs["value"]),
                })
            except (KeyError, ValueError):
                continue

    return pd.DataFrame(records)


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
    log.info("=== pull_bls: START ===")
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    states  = list(BLS_STATE_SERIES.keys())
    series  = list(BLS_STATE_SERIES.values())

    all_frames = []

    # Batch into groups of BATCH_SIZE
    for i in range(0, len(series), BATCH_SIZE):
        batch_series = series[i:i + BATCH_SIZE]
        batch_states = states[i:i + BATCH_SIZE]
        log.info(f"BLS batch {i // BATCH_SIZE + 1}: {len(batch_series)} states")

        try:
            df_batch = fetch_bls_batch(batch_series, batch_states)
            if not df_batch.empty:
                all_frames.append(df_batch)
                log.info(f"  → {len(df_batch)} observations")
        except requests.RequestException as e:
            log.error(f"BLS batch {i // BATCH_SIZE + 1} failed: {e}")

        # BLS rate limiting — be polite
        if i + BATCH_SIZE < len(series):
            time.sleep(1)

    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
    else:
        log.warning("BLS returned no data")
        combined = pd.DataFrame(columns=["state", "series_id", "year", "month",
                                          "period_name", "unemployment_rate"])

    combined["source"]     = "BLS"
    combined["fetched_at"] = run_ts

    # Save locally
    out_path    = BRONZE_DIR / f"bls_bronze_{run_ts}.csv"
    latest_path = BRONZE_DIR / "bls_bronze_latest.csv"
    combined.to_csv(out_path, index=False)
    combined.to_csv(latest_path, index=False)
    log.info(f"Bronze CSV saved: {out_path} ({len(combined)} rows)")

    # Upload to S3
    upload_to_s3(out_path,    f"{S3_BRONZE_PREFIX}/bls/bls_bronze_{run_ts}.csv")
    upload_to_s3(latest_path, f"{S3_BRONZE_PREFIX}/bls/bls_bronze_latest.csv")

    log.info(f"=== pull_bls: COMPLETE — {len(combined)} rows, {combined['state'].nunique() if not combined.empty else 0} states ===")
    return str(out_path)


if __name__ == "__main__":
    run()
