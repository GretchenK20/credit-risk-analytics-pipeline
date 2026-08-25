"""
Credit Risk Analytics Pipeline - Configuration
Author: Gretchen Kolthoff
"""

import os
from pathlib import Path

# ── Project paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR   = DATA_DIR / "gold"
VIZ_DIR    = BASE_DIR / "viz"

# ── AWS S3 ─────────────────────────────────────────────────────────────────────
S3_BUCKET        = os.getenv("S3_BUCKET", "credit-risk-pipeline-gk")
S3_BRONZE_PREFIX = "bronze"
S3_SILVER_PREFIX = "silver"
S3_GOLD_PREFIX   = "gold"
AWS_REGION       = os.getenv("AWS_REGION", "us-east-1")

# ── FRED API ───────────────────────────────────────────────────────────────────
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# FRED series — each series_id must be unique (no duplicate values)
FRED_SERIES = {
    "delinquency_all":             "DRCCLACBS",  # Delinquency Rate, Consumer Loans
    "chargeoff_all":               "CORCLACBS",  # Charge-off Rate, Consumer Loans
    "chargeoff_credit_card":       "CORCACBS",   # Charge-off Rate, Credit Cards
    "fed_funds_rate":              "FEDFUNDS",   # Federal Funds Effective Rate
    "unemployment_rate":           "UNRATE",     # US Unemployment Rate
    "cpi":                         "CPIAUCSL",   # Consumer Price Index
    "consumer_credit_outstanding": "TOTALSL",    # Total Consumer Credit Outstanding
}

FRED_START_DATE = "2014-01-01"
FRED_END_DATE   = "2024-12-31"

# ── FDIC BankFind API ──────────────────────────────────────────────────────────
FDIC_BASE_URL = "https://banks.data.fdic.gov/api"

FDIC_FIELDS = [
    "REPDTE", "ASSET", "DEP", "LNLSNET",
    "NETINC", "INTINC", "EINTEXP",
    "LNLSDEPR", "LNLSDEPP", "NETCHARGE", "REPNO",
]

FDIC_START_DATE = "20140101"
FDIC_END_DATE   = "20241231"

# ── BLS API ────────────────────────────────────────────────────────────────────
BLS_API_KEY  = os.getenv("BLS_API_KEY", "")
BLS_BASE_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

BLS_STATE_SERIES = {
    "Alabama":              "LAUST010000000000003",
    "Alaska":               "LAUST020000000000003",
    "Arizona":              "LAUST040000000000003",
    "Arkansas":             "LAUST050000000000003",
    "California":           "LAUST060000000000003",
    "Colorado":             "LAUST080000000000003",
    "Connecticut":          "LAUST090000000000003",
    "Delaware":             "LAUST100000000000003",
    "Florida":              "LAUST120000000000003",
    "Georgia":              "LAUST130000000000003",
    "Hawaii":               "LAUST150000000000003",
    "Idaho":                "LAUST160000000000003",
    "Illinois":             "LAUST170000000000003",
    "Indiana":              "LAUST180000000000003",
    "Iowa":                 "LAUST190000000000003",
    "Kansas":               "LAUST200000000000003",
    "Kentucky":             "LAUST210000000000003",
    "Louisiana":            "LAUST220000000000003",
    "Maine":                "LAUST230000000000003",
    "Maryland":             "LAUST240000000000003",
    "Massachusetts":        "LAUST250000000000003",
    "Michigan":             "LAUST260000000000003",
    "Minnesota":            "LAUST270000000000003",
    "Mississippi":          "LAUST280000000000003",
    "Missouri":             "LAUST290000000000003",
    "Montana":              "LAUST300000000000003",
    "Nebraska":             "LAUST310000000000003",
    "Nevada":               "LAUST320000000000003",
    "New Hampshire":        "LAUST330000000000003",
    "New Jersey":           "LAUST340000000000003",
    "New Mexico":           "LAUST350000000000003",
    "New York":             "LAUST360000000000003",
    "North Carolina":       "LAUST370000000000003",
    "North Dakota":         "LAUST380000000000003",
    "Ohio":                 "LAUST390000000000003",
    "Oklahoma":             "LAUST400000000000003",
    "Oregon":               "LAUST410000000000003",
    "Pennsylvania":         "LAUST420000000000003",
    "Rhode Island":         "LAUST440000000000003",
    "South Carolina":       "LAUST450000000000003",
    "South Dakota":         "LAUST460000000000003",
    "Tennessee":            "LAUST470000000000003",
    "Texas":                "LAUST480000000000003",
    "Utah":                 "LAUST490000000000003",
    "Vermont":              "LAUST500000000000003",
    "Virginia":             "LAUST510000000000003",
    "Washington":           "LAUST530000000000003",
    "West Virginia":        "LAUST540000000000003",
    "Wisconsin":            "LAUST550000000000003",
    "Wyoming":              "LAUST560000000000003",
    "District of Columbia": "LAUST110000000000003",
}

BLS_START_YEAR = "2014"
BLS_END_YEAR   = "2024"

# ── Data quality thresholds ────────────────────────────────────────────────────
MAX_NULL_PCT        = 0.05
MIN_ROWS_FRED       = 100
MIN_ROWS_FDIC       = 10
MIN_ROWS_BLS        = 40
ZSCORE_OUTLIER_FLAG = 3.5
