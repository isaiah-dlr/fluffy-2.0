# aggregations.py
from __future__ import annotations

from typing import List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

from . import config
from .data_prep import Granularity, Mode, ResolvedWindow, week_start_monday, month_start


def _entity_col(mode: Mode) -> str:
    return "entity_agency" if mode == "Agency" else "entity_region"


def _make_period_key(series: pd.Series, granularity: Granularity) -> pd.Series:
    if granularity == "Weekly":
        return series.apply(week_start_monday)
    if granularity == "Monthly":
        return series.apply(month_start)
    if granularity == "Yearly":
        # Use FY start date as period_key for consistency
        fy = series.apply(lambda x: None)
        raise ValueError("Yearly period_key should be precomputed via fiscal_year in caller.")
    raise ValueError("Unsupported granularity")


def _fy_start_from_fy(fy: pd.Series) -> pd.Series:
    # FY start = (fy-1)-07-01
    return pd.to_datetime((fy.astype(int) - 1).astype(str) + "-07-01")


def filter_base(
    df: pd.DataFrame,
    mode: Mode,
    selected_entities: List[str],
    window: ResolvedWindow,
    granularity: Granularity,
) -> pd.DataFrame:
    entity_col = _entity_col(mode)
    out = df.copy()

    # Date filter
    out = out[(out["date"] >= window.start_date) & (out["date"] <= window.end_date)]

    # Entity filter
    selected_set = set([str(x) for x in selected_entities])
    out = out[out[entity_col].astype(str).isin(selected_set)]

    # Period key
    if granularity == "Weekly":
        out["period_key"] = out["date"].apply(week_start_monday)
    elif granularity == "Monthly":
        out["period_key"] = out["date"].apply(month_start)
    elif granularity == "Yearly":
        out["period_key"] = _fy_start_from_fy(out["fiscal_year"])
    else:
        raise ValueError("Unsupported granularity")

    out["entity_id"] = out[entity_col].astype(str)

    return out


def agg_entity_period(base: pd.DataFrame) -> pd.DataFrame:
    # One row per entity_id x period_key
    def _median_ignore_null(s):
        s2 = pd.to_numeric(s, errors="coerce")
        s2 = s2.dropna()
        if len(s2) == 0:
            return np.nan
        return float(s2.median())

    grp = base.groupby(["entity_id", "period_key"], as_index=False)
    out = grp.agg(
        lbs=("gross_weight", "sum"),
        hh_median=("hh_size", _median_ignore_null),
        hh_max=("hh_size", lambda s: pd.to_numeric(s, errors="coerce").max()),
        order_count=("gross_weight", "size"),
        hh_nonnull_count=("hh_size", lambda s: pd.to_numeric(s, errors="coerce").notna().sum()),
    )

    # Buckets from computed numeric metrics
    out["hh_median_bucket"] = out["hh_median"].apply(_bucket_from_numeric)
    out["hh_max_bucket"] = out["hh_max"].apply(_bucket_from_numeric)

    return out


def agg_entity_range(base: pd.DataFrame, period_keys: List[pd.Timestamp]) -> pd.DataFrame:
    # Compute range stats per entity across the selected window
    # Range-average baseline is average of period lbs across period_keys (including zero periods if missing? choose: observed only)
    # We'll compute using observed periods; UI can show periods_in_range.
    ep = agg_entity_period(base)
    grp = ep.groupby("entity_id", as_index=False)
    out = grp.agg(
        lbs_range_total=("lbs", "sum"),
        lbs_range_avg=("lbs", "mean"),
    )
    out["periods_observed"] = grp.size()["size"] if "size" in grp.size() else grp.size()

    # HH stats over all orders (not period medians)
    def _median_all(s):
        s2 = pd.to_numeric(s, errors="coerce").dropna()
        if len(s2) == 0:
            return np.nan
        return float(s2.median())

    grp2 = base.groupby("entity_id", as_index=False)
    hh = grp2.agg(
        hh_median_range=("hh_size", _median_all),
        hh_max_range=("hh_size", lambda s: pd.to_numeric(s, errors="coerce").max()),
    )
    hh["hh_median_range_bucket"] = hh["hh_median_range"].apply(_bucket_from_numeric)
    hh["hh_max_range_bucket"] = hh["hh_max_range"].apply(_bucket_from_numeric)

    out = out.merge(hh, on="entity_id", how="left")
    return out


def _safe_pct_change(current: float, baseline: float) -> float:
    # Returns pct change; uses inf when baseline is 0 and current != 0
    if baseline is None or np.isnan(baseline):
        return np.nan
    if baseline == 0:
        if current == 0:
            return 0.0
        return np.inf if current > 0 else -np.inf
    return (current - baseline) / abs(baseline)


def add_deltas(entity_period: pd.DataFrame, entity_range: pd.DataFrame) -> pd.DataFrame:
    # Adds PoP and RangeAvg deltas and flag_pop_20
    ep = entity_period.sort_values(["entity_id", "period_key"]).copy()
    ep["lbs_prev"] = ep.groupby("entity_id")["lbs"].shift(1)

    ep["pop_delta_lbs"] = ep["lbs"] - ep["lbs_prev"]
    ep["pop_delta_pct"] = [
        _safe_pct_change(c, b) for c, b in zip(ep["lbs"].astype(float), ep["lbs_prev"].astype(float))
    ]

    ep = ep.merge(entity_range[["entity_id", "lbs_range_avg"]], on="entity_id", how="left")
    ep["rng_delta_lbs"] = ep["lbs"] - ep["lbs_range_avg"]
    ep["rng_delta_pct"] = [
        _safe_pct_change(c, b) for c, b in zip(ep["lbs"].astype(float), ep["lbs_range_avg"].astype(float))
    ]

    ep["flag_pop_20"] = ep["pop_delta_pct"].apply(lambda x: False if pd.isna(x) else (abs(x) >= 0.20))

    return ep


def _bucket_from_numeric(x) -> Optional[str]:
    try:
        if pd.isna(x):
            return None
        v = float(x)
    except Exception:
        return None
    for label, lo, hi in config.HH_BUCKETS:
        if v >= lo and v <= hi:
            return label
    return "XL"


def build_prior_fy_aligned(
    df: pd.DataFrame,
    mode: Mode,
    selected_entities: List[str],
    window: ResolvedWindow,
    granularity: Granularity,
) -> pd.DataFrame:
    # Prior fiscal-year same-dates series, aligned to current period_key axis.
    # Strategy:
    # - Take prior-year records that fall within [start_date-1y, end_date-1y]
    # - Compute their "native" period_key, then compute "aligned_period_key" by shifting +1y and re-bucketing.
    if granularity not in ("Weekly", "Monthly"):
        raise ValueError("Prior FY alignment is only supported for Weekly/Monthly views.")

    start_prior = (window.start_date - pd.DateOffset(years=1)).normalize()
    end_prior = (window.end_date - pd.DateOffset(years=1)).normalize()

    entity_col = _entity_col(mode)
    selected_set = set([str(x) for x in selected_entities])

    prior = df.copy()
    prior = prior[(prior["date"] >= start_prior) & (prior["date"] <= end_prior)]
    prior = prior[prior[entity_col].astype(str).isin(selected_set)]
    prior["entity_id"] = prior[entity_col].astype(str)

    if granularity == "Weekly":
        prior["period_key_native"] = prior["date"].apply(week_start_monday)
        # align forward 1 year and re-Monday
        prior["aligned_period_key"] = (prior["period_key_native"] + pd.DateOffset(years=1)).apply(week_start_monday)
    else:
        prior["period_key_native"] = prior["date"].apply(month_start)
        prior["aligned_period_key"] = (prior["period_key_native"] + pd.DateOffset(years=1)).apply(month_start)

    # Aggregate by aligned key (so it can join with current axis)
    def _median_ignore_null(s):
        s2 = pd.to_numeric(s, errors="coerce").dropna()
        if len(s2) == 0:
            return np.nan
        return float(s2.median())

    grp = prior.groupby(["entity_id", "aligned_period_key"], as_index=False)
    out = grp.agg(
        lbs_prior=("gross_weight", "sum"),
        hh_median_prior=("hh_size", _median_ignore_null),
        hh_max_prior=("hh_size", lambda s: pd.to_numeric(s, errors="coerce").max()),
    )
    out["hh_median_prior_bucket"] = out["hh_median_prior"].apply(_bucket_from_numeric)
    out["hh_max_prior_bucket"] = out["hh_max_prior"].apply(_bucket_from_numeric)

    out = out.rename(columns={"aligned_period_key": "period_key"})
    return out


def add_prior_and_did(current_with_deltas: pd.DataFrame, prior_aligned: pd.DataFrame) -> pd.DataFrame:
    # Join prior series and compute prior deltas + DiD
    out = current_with_deltas.merge(prior_aligned, on=["entity_id", "period_key"], how="left")

    # Prior PoP (computed within the aligned axis)
    out = out.sort_values(["entity_id", "period_key"]).copy()
    out["lbs_prior_prev"] = out.groupby("entity_id")["lbs_prior"].shift(1)

    out["pop_delta_lbs_prior"] = out["lbs_prior"] - out["lbs_prior_prev"]
    out["pop_delta_pct_prior"] = [
        _safe_pct_change(c, b)
        for c, b in zip(out["lbs_prior"].astype(float), out["lbs_prior_prev"].astype(float))
    ]

    # Prior range average baseline: average of prior series over the aligned window (per entity)
    prior_avg = out.groupby("entity_id", as_index=False).agg(lbs_range_avg_prior=("lbs_prior", "mean"))
    out = out.merge(prior_avg, on="entity_id", how="left")

    out["rng_delta_lbs_prior"] = out["lbs_prior"] - out["lbs_range_avg_prior"]
    out["rng_delta_pct_prior"] = [
        _safe_pct_change(c, b)
        for c, b in zip(out["lbs_prior"].astype(float), out["lbs_range_avg_prior"].astype(float))
    ]

    out["did_pop_pct"] = out["pop_delta_pct"] - out["pop_delta_pct_prior"]
    out["did_rng_pct"] = out["rng_delta_pct"] - out["rng_delta_pct_prior"]

    return out
