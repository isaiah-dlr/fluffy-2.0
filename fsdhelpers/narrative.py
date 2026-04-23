# narrative.py
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .charts import period_label

def _per_period_word(granularity: str) -> str:
    g = (granularity or "").strip().lower()
    if g == "weekly":
        return "per week"
    if g == "monthly":
        return "per month"
    if g == "yearly":
        return "per year"
    return "per period"

def _fmt_int(x):
    return "" if pd.isna(x) else f"{float(x):,.0f}"

def _fmt_pct_from_ratio(r):
    # r is ratio like 0.123 => 12.3%
    if pd.isna(r):
        return ""
    if r == float("inf"):
        return "∞"
    if r == float("-inf"):
        return "-∞"
    return f"{r*100:.1f}%"

def _safe_ratio_trend(first, last):
    # Returns ratio (e.g., 0.10 = +10%) or np.nan if undefined
    if pd.isna(first) or pd.isna(last):
        return np.nan
    if first == 0:
        return np.nan
    return (last - first) / abs(first)

def build_narrative(epd: pd.DataFrame, granularity: str, include_prior: bool) -> str:
    if epd is None or len(epd) == 0:
        return "No data available for the selected filters."

    df = epd.copy()

    # Ensure period labels exist
    if "period_label" not in df.columns:
        df["period_label"] = df["period_key"].apply(lambda k: period_label(granularity, k))

    lines = []
    for entity_id, g in df.groupby("entity_id", sort=True):
        g = g.sort_values("period_key").copy()

        lbs = pd.to_numeric(g["lbs"], errors="coerce")
        total_lbs = lbs.sum(skipna=True)
        avg_lbs = lbs.mean(skipna=True)

        # Trend: compare first non-null vs last non-null (interpretable)
        nonnull = g.loc[lbs.notna()]
        first_val = nonnull["lbs"].iloc[0] if len(nonnull) else np.nan
        last_val  = nonnull["lbs"].iloc[-1] if len(nonnull) else np.nan

        n_steps = max(len(nonnull) - 1, 0)
        total_ratio = _safe_ratio_trend(first_val, last_val)

        per_word = _per_period_word(granularity)
        period = per_word.split()[-1] if len(per_word.split()) > 1 else "period"

        if pd.isna(total_ratio) or n_steps == 0:
            trend_phrase = "Overall trend is not directly comparable (insufficient periods or starts at 0)."
        else:
            # geometric average change per step (compounded)
            if first_val <= 0 or last_val < 0:
                trend_phrase = "Overall trend is not directly comparable (non-positive values in trend calculation)."
            else:
                per_period_ratio = (last_val / first_val) ** (1 / n_steps) - 1

                direction = (
                    "increased" if total_ratio > 0
                    else "decreased" if total_ratio < 0
                    else "remained roughly stable"
                )

                trend_phrase = (
                    f"Over time, distribution generally {direction} by "
                    f"{_fmt_pct_from_ratio(abs(per_period_ratio))} {per_word}, "
                    f"totaling {_fmt_pct_from_ratio(abs(total_ratio))} from the first to the last {period}."
                )

        # Volatility / flags
        flagged_n = 0
        if "flag_pop_20" in g.columns:
            flagged_n = int(g["flag_pop_20"].fillna(False).sum())

        # Largest PoP increase/decrease using pop_delta_pct
        inc_txt = "Largest increase: not available."
        dec_txt = "Largest decrease: not available."
        if "pop_delta_pct" in g.columns:
            pop = pd.to_numeric(g["pop_delta_pct"], errors="coerce")

            # Ignore inf when selecting max/min if you prefer; but keep for display if it wins.
            idx_max = pop.idxmax(skipna=True) if pop.notna().any() else None
            idx_min = pop.idxmin(skipna=True) if pop.notna().any() else None

            if idx_max is not None and pd.notna(idx_max):
                r = pop.loc[idx_max]
                p = g.loc[idx_max, "period_label"]
                y = g.loc[idx_max, "lbs"]
                inc_txt = f"Largest increase: {p} ({_fmt_int(y)} lbs, {_fmt_pct_from_ratio(r)} vs previous {period})."

            if idx_min is not None and pd.notna(idx_min):
                r = pop.loc[idx_min]
                p = g.loc[idx_min, "period_label"]
                y = g.loc[idx_min, "lbs"]
                dec_txt = f"Largest decrease: {p} ({_fmt_int(y)} lbs, {_fmt_pct_from_ratio(r)} vs previous {period})."

        # Earliest period
        earliest_period = g["period_label"].iloc[0]
        earliest_lbs = g["lbs"].iloc[0]
        first_day = earliest_period.split(" to ")[0] if " to " in earliest_period else earliest_period
        
        # Most recent period
        recent_period = g["period_label"].iloc[-1]
        recent_lbs = g["lbs"].iloc[-1]
        last_day  = recent_period.split(" to ")[1] if " to " in recent_period else recent_period
        
        # Optional prior FY quick context (kept minimal)
        prior_txt = ""
        if include_prior and "lbs_prior" in g.columns:
            lbs_prior = pd.to_numeric(g["lbs_prior"], errors="coerce")
            prior_total = lbs_prior.sum(skipna=True)
            prior_txt = f" Prior FY total (aligned): {_fmt_int(prior_total)} lbs."

        # Compose a compact executive summary
        lines.append(f"{entity_id} for the period {first_day} to {last_day}:")
        lines.append(f"- Total pounds distributed: {_fmt_int(total_lbs)} lbs. The average {per_word} was {_fmt_int(avg_lbs)} lbs.{prior_txt}")
        lines.append(f"- {trend_phrase}")
        lines.append(f"- {inc_txt}")
        lines.append(f"- {dec_txt}")
        lines.append(f"- Number of {period}(s) with >20% increase/decrease vs previous {period}: {flagged_n}.")
        lines.append(f"- Most recent {period} ({recent_period}) pounds distributed: {_fmt_int(recent_lbs)} lbs.")
        lines.append("")  # spacer between entities

    return "\n".join(lines).strip()