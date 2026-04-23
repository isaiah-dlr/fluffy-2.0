# data_prep.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Literal

import pandas as pd

from . import config


Mode = Literal["Agency", "Region"]
Granularity = Literal["Weekly", "Monthly", "Yearly"]


@dataclass(frozen=True)
class ResolvedWindow:
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    period_keys: List[pd.Timestamp]  # sorted
    granularity: Granularity


def load_dataset(path: str) -> pd.DataFrame:
    if not path:
        raise ValueError("DATA_PATH is empty. Set config.DATA_PATH or enter a path in the app.")

    p = path.strip().strip('"').strip("'")
    if p.lower().endswith(".csv"):
        try:
            df = pd.read_csv(p, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(p, encoding="latin-1")
    elif p.lower().endswith(".xlsx") or p.lower().endswith(".xls"):
        df = pd.read_excel(p)
    else:
        raise ValueError("Unsupported file type. Use .csv or .xlsx")

    required = [
        config.COL_DATE,
        config.COL_BILL_TO_AGENCY,
        config.COL_REGION,
        config.COL_HH_CODE,
        config.COL_GROSS_WEIGHT,
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Parse date
    df[config.COL_DATE] = pd.to_datetime(df[config.COL_DATE], errors="coerce")
    if df[config.COL_DATE].isna().all():
        raise ValueError("Could not parse any dates from the Date column.")

    # Numeric weight
    w = df[config.COL_GROSS_WEIGHT].astype(str).str.strip()

    # remove thousands separators and stray spaces
    w = w.str.replace(",", "", regex=False)

    df[config.COL_GROSS_WEIGHT] = pd.to_numeric(w, errors="coerce").fillna(0.0)

    return df


def compute_fiscal_year_from_date(date_series: pd.Series) -> pd.Series:
    # FY starts July 1. If month >= 7 => FY = year + 1 else year.
    y = date_series.dt.year
    m = date_series.dt.month
    return (y + (m >= 7).astype(int)).astype("Int64")


def parse_hh_size(value) -> Optional[int]:
    if pd.isna(value):
        return None
    # If it's already numeric-like
    try:
        # Handles ints, floats, numeric strings
        n = int(float(str(value).strip()))
        return n
    except Exception:
        pass

    s = str(value).strip()

    # Primary format: "67D 130P" -> 130
    m = re.search(r"(\d+)\s*P\b", s, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None

    # As a fallback, extract first integer if present
    m2 = re.search(r"(\d+)", s)
    if m2:
        try:
            return int(m2.group(1))
        except Exception:
            return None

    return None


def bucket_hh_size(hh: Optional[int]) -> Optional[str]:
    if hh is None:
        return None
    for label, lo, hi in config.HH_BUCKETS:
        if hh >= lo and hh <= hi:
            return label
    return "XL"


def week_start_monday(ts: pd.Timestamp) -> pd.Timestamp:
    # Monday = 0
    return (ts - pd.to_timedelta(ts.weekday(), unit="D")).normalize()


def month_start(ts: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(year=ts.year, month=ts.month, day=1)


def fiscal_year_start(fy: int) -> pd.Timestamp:
    # FY 2024 starts 2023-07-01
    return pd.Timestamp(year=fy - 1, month=7, day=1)


def fiscal_year_end(fy: int) -> pd.Timestamp:
    # FY ends June 30 of FY year
    return pd.Timestamp(year=fy, month=6, day=30)


def add_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["date"] = out[config.COL_DATE]
    out["fiscal_year"] = compute_fiscal_year_from_date(out["date"])
    out["entity_agency"] = out[config.COL_BILL_TO_AGENCY].astype(str)
    out["entity_region"] = out[config.COL_REGION].astype(str)

    out["gross_weight"] = out[config.COL_GROSS_WEIGHT].astype(float)

    out["hh_size"] = out[config.COL_HH_CODE].apply(parse_hh_size)
    out["hh_bucket"] = out["hh_size"].apply(bucket_hh_size)

    return out


def resolve_window(
    df: pd.DataFrame,
    granularity: Granularity,
    mode: str,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
    anchor_date: Optional[pd.Timestamp] = None,
    lookback_periods: Optional[int] = None,
) -> ResolvedWindow:
    # Resolve to a concrete start/end and a list of period keys.
    if (start_date is None) != (end_date is None):
        raise ValueError("Provide both start_date and end_date, or neither.")
    if start_date is not None and end_date is not None:
        sd = pd.to_datetime(start_date).normalize()
        ed = pd.to_datetime(end_date).normalize()
        if ed < sd:
            raise ValueError("End date cannot be before start date.")
    else:
        if anchor_date is None or lookback_periods is None:
            raise ValueError("Provide anchor_date and lookback_periods when not using a date range.")
        a = pd.to_datetime(anchor_date).normalize()
        n = int(lookback_periods)
        if n < 0:
            raise ValueError("lookback_periods must be >= 0.")

        if granularity == "Weekly":
            a_key = week_start_monday(a)
            keys = [a_key - pd.Timedelta(days=7 * i) for i in range(n + 1)]
            keys = sorted(set(keys))
            sd = keys[0]
            ed = keys[-1] + pd.Timedelta(days=6)
            return ResolvedWindow(sd, ed, keys, granularity)

        if granularity == "Monthly":
            a_key = month_start(a)
            keys = [a_key - pd.DateOffset(months=i) for i in range(n + 1)]
            keys = sorted({pd.Timestamp(k) for k in keys})
            sd = keys[0]
            ed = (keys[-1] + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
            return ResolvedWindow(sd, ed, keys, granularity)

        if granularity == "Yearly":
            # Anchor determines FY; include N previous FYs
            fy = int(compute_fiscal_year_from_date(pd.Series([a]))[0])
            fys = sorted({fy - i for i in range(n + 1)})
            keys = [fiscal_year_start(f) for f in fys]  # period_key as FY start
            sd = fiscal_year_start(fys[0])
            ed = fiscal_year_end(fys[-1])
            return ResolvedWindow(sd, ed, keys, granularity)

    # Date range path: build period keys that intersect the range
    if granularity == "Weekly":
        start_key = week_start_monday(sd)
        end_key = week_start_monday(ed)
        keys = []
        k = start_key
        while k <= end_key:
            keys.append(k)
            k = k + pd.Timedelta(days=7)
        return ResolvedWindow(sd, ed, keys, granularity)

    if granularity == "Monthly":
        start_key = month_start(sd)
        end_key = month_start(ed)
        keys = []
        k = start_key
        while k <= end_key:
            keys.append(k)
            k = (k + pd.DateOffset(months=1))
            k = pd.Timestamp(k)
        return ResolvedWindow(sd, ed, keys, granularity)

    if granularity == "Yearly":
        # Determine FYs that overlap the range
        fy_start = int(compute_fiscal_year_from_date(pd.Series([sd]))[0])
        fy_end = int(compute_fiscal_year_from_date(pd.Series([ed]))[0])
        fys = list(range(fy_start, fy_end + 1))
        keys = [fiscal_year_start(f) for f in fys]
        return ResolvedWindow(sd, ed, keys, granularity)

    raise ValueError("Unsupported granularity")
