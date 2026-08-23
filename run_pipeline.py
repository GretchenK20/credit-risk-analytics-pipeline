"""
Standalone pipeline runner.
Executes all tasks in DAG order without requiring Airflow to be installed.
Use this for local development and demo; the DAG file handles Airflow deployment.

Usage:
    python run_pipeline.py                  # full pipeline
    python run_pipeline.py --skip-extract   # transforms + gold only (bronze already exists)
    python run_pipeline.py --gold-only      # gold mart rebuild only
"""

import argparse
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log"),
    ]
)
log = logging.getLogger("run_pipeline")

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_task(name: str, fn, *args, **kwargs):
    """Wrapper: time a task, log result, raise on failure."""
    log.info(f"\n{'='*60}")
    log.info(f"TASK START: {name}")
    log.info(f"{'='*60}")
    t0 = time.time()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.time() - t0
        log.info(f"TASK COMPLETE: {name} ({elapsed:.1f}s) → {result}")
        return result
    except Exception as e:
        elapsed = time.time() - t0
        log.error(f"TASK FAILED: {name} ({elapsed:.1f}s) — {e}")
        raise


def validate_bronze():
    """Quality gate between extract and transform."""
    from config import BRONZE_DIR
    import os
    required = [
        BRONZE_DIR / "fred_bronze_latest.csv",
        BRONZE_DIR / "fdic_bronze_latest.csv",
        BRONZE_DIR / "bls_bronze_latest.csv",
    ]
    missing = [str(p) for p in required if not p.exists()]
    empty   = [str(p) for p in required if p.exists() and os.path.getsize(p) < 100]

    if missing:
        raise FileNotFoundError(f"Bronze files missing: {missing}")
    if empty:
        raise ValueError(f"Bronze files appear empty: {empty}")
    log.info("Quality gate PASSED — all bronze files present")


def main():
    parser = argparse.ArgumentParser(description="Credit Risk Pipeline Runner")
    parser.add_argument("--skip-extract", action="store_true",
                        help="Skip API pulls (use existing bronze files)")
    parser.add_argument("--gold-only",    action="store_true",
                        help="Only rebuild gold mart from existing silver")
    args = parser.parse_args()

    from tasks.pull_fred          import run as pull_fred
    from tasks.pull_fdic          import run as pull_fdic
    from tasks.pull_bls           import run as pull_bls
    from tasks.transform_fred     import run as transform_fred
    from tasks.transform_fdic_bls import run as transform_fdic_bls
    from tasks.build_gold_mart    import run as build_gold_mart

    pipeline_start = time.time()

    if not args.gold_only and not args.skip_extract:
        # ── Extract (parallel in Airflow; sequential here) ─────────────────
        run_task("pull_fred",  pull_fred)
        run_task("pull_fdic",  pull_fdic)
        run_task("pull_bls",   pull_bls)
        run_task("validate_bronze_quality", validate_bronze)

    if not args.gold_only:
        # ── Transform ──────────────────────────────────────────────────────
        run_task("transform_fred",      transform_fred)
        run_task("transform_fdic_bls",  transform_fdic_bls)

    # ── Gold ───────────────────────────────────────────────────────────────
    run_task("build_gold_mart", build_gold_mart)

    total = time.time() - pipeline_start
    log.info(f"\n{'='*60}")
    log.info(f"PIPELINE COMPLETE in {total:.1f}s")
    log.info(f"Gold marts ready in: {PROJECT_ROOT / 'data' / 'gold'}")
    log.info(f"{'='*60}")


if __name__ == "__main__":
    main()
