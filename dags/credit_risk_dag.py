"""
Credit Risk Analytics Pipeline — Airflow DAG
Author: Gretchen Kolthoff


DAG Architecture:
    pull_fred ──┐
    pull_fdic ──┼──► validate_quality ──► transform_fred ──┐
    pull_bls  ──┘                      ──► transform_fdic_bls ──┤
                                                                 └──► build_gold_mart
                                                                           │
                                                                    ┌──────┴──────┐
                                                               quarterly_mart  scatter_mart
                                                               (Bokeh Viz 1)  (Tableau Viz 3)
                                                               bls_choropleth (Bokeh Viz 2)


"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ── Airflow imports (graceful fallback if not installed) ──────────────────────
try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    logging.warning("Airflow not installed — DAG defined but not registerable. "
                    "Run tasks directly via run_pipeline.py")

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Task imports ──────────────────────────────────────────────────────────────
from tasks.pull_fred        import run as pull_fred
from tasks.pull_fdic        import run as pull_fdic
from tasks.pull_bls         import run as pull_bls
from tasks.transform_fred   import run as transform_fred
from tasks.transform_fdic_bls import run as transform_fdic_bls
from tasks.build_gold_mart  import run as build_gold_mart

# ── Validate quality (lightweight gate task) ──────────────────────────────────
def validate_quality(**context):
    """
    Gate task: verify all three bronze files exist and have non-zero size
    before allowing transforms to proceed.
    Mirrors production data quality gate patterns.
    """
    from config import BRONZE_DIR
    import os

    required = [
        BRONZE_DIR / "fred_bronze_latest.csv",
        BRONZE_DIR / "fdic_bronze_latest.csv",
        BRONZE_DIR / "bls_bronze_latest.csv",
    ]

    missing  = []
    empty    = []

    for path in required:
        if not path.exists():
            missing.append(str(path))
        elif os.path.getsize(path) < 100:   # <100 bytes = effectively empty
            empty.append(str(path))

    if missing:
        raise FileNotFoundError(f"Bronze files missing: {missing}")
    if empty:
        raise ValueError(f"Bronze files appear empty: {empty}")

    logging.info(f"Quality gate PASSED: all {len(required)} bronze files present and non-empty")
    return True


# ── DAG definition ─────────────────────────────────────────────────────────────
if AIRFLOW_AVAILABLE:
    default_args = {
        "owner":            "gretchen_kolthoff",
        "depends_on_past":  False,
        "email_on_failure": False,
        "email_on_retry":   False,
        "retries":          2,
        "retry_delay":      timedelta(minutes=5),
    }

    with DAG(
        dag_id="credit_risk_analytics_pipeline",
        default_args=default_args,
        description=(
            "Multi-source consumer credit risk pipeline: "
            "FRED + FDIC BankFind + BLS → S3 medallion (bronze/silver/gold) → Bokeh + Tableau"
        ),
        schedule_interval=None,       # Manual trigger; set to "@monthly" for production
        start_date=datetime(2024, 1, 1),
        catchup=False,
        tags=["credit-risk", "banking", "data-engineering", "portfolio"],
    ) as dag:

        # ── Extract tasks (run in parallel) ───────────────────────────────────
        t_pull_fred = PythonOperator(
            task_id="pull_fred",
            python_callable=pull_fred,
            doc_md="Pull FRED API series (delinquency, charge-offs, fed funds, unemployment, CPI) → S3 bronze/fred/",
        )

        t_pull_fdic = PythonOperator(
            task_id="pull_fdic",
            python_callable=pull_fdic,
            doc_md="Pull FDIC BankFind aggregate banking financials → S3 bronze/fdic/",
        )

        t_pull_bls = PythonOperator(
            task_id="pull_bls",
            python_callable=pull_bls,
            doc_md="Pull BLS state unemployment rates (50 states + DC) → S3 bronze/bls/",
        )

        # ── Quality gate (all three pulls must complete) ───────────────────────
        t_validate = PythonOperator(
            task_id="validate_bronze_quality",
            python_callable=validate_quality,
            doc_md="Gate: verify all bronze files are present and non-empty before transforms.",
        )

        # ── Transform tasks ───────────────────────────────────────────────────
        t_transform_fred = PythonOperator(
            task_id="transform_fred",
            python_callable=transform_fred,
            doc_md="Clean FRED data: null handling, outlier flagging, rate regime classification → S3 silver/fred/",
        )

        t_transform_fdic_bls = PythonOperator(
            task_id="transform_fdic_bls",
            python_callable=transform_fdic_bls,
            doc_md="Clean FDIC + BLS data: numeric coercion, annual aggregation, state rankings → S3 silver/",
        )

        # ── Gold mart ─────────────────────────────────────────────────────────
        t_gold_mart = PythonOperator(
            task_id="build_gold_mart",
            python_callable=build_gold_mart,
            doc_md=(
                "Join FRED + FDIC → quarterly analytics mart. "
                "Export scatter mart (Tableau) and BLS choropleth mart (Bokeh). "
                "→ S3 gold/"
            ),
        )

        # ── Task dependencies ─────────────────────────────────────────────────
        # Parallel extract → quality gate → parallel transform → gold
        [t_pull_fred, t_pull_fdic, t_pull_bls] >> t_validate
        t_validate >> [t_transform_fred, t_transform_fdic_bls]
        [t_transform_fred, t_transform_fdic_bls] >> t_gold_mart
