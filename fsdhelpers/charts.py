# charts.py
from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go


def period_label(granularity: str, period_key: pd.Timestamp) -> str:
    if granularity == "Weekly":
        start = pd.Timestamp(period_key).date()
        end = (pd.Timestamp(period_key) + pd.Timedelta(days=6)).date()
        return f"{start} to {end}"
    if granularity == "Monthly":
        return pd.Timestamp(period_key).strftime("%Y-%m")
    if granularity == "Yearly":
        # period_key is FY start
        fy = pd.Timestamp(period_key).year + 1  # FY year = start year + 1
        return f"FY {fy}"
    return str(period_key)


def make_entity_chart(df_entity: pd.DataFrame, granularity: str, include_prior: bool) -> go.Figure:
    df_entity = df_entity.sort_values("period_key").copy()
    x = [period_label(granularity, k) for k in df_entity["period_key"]]

    fig = go.Figure()

    # Bars: current
    fig.add_trace(
        go.Bar(
            x=x,
            y=df_entity["lbs"],
            name="Current FY",
            hovertemplate="%{x}<br>%{y:,.0f} Lbs (Current FY)<extra></extra>",
        )
    )

    # Optional prior line
    if include_prior and "lbs_prior" in df_entity.columns:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=df_entity["lbs_prior"],
                mode="lines+markers",
                line=dict(color="orange", width=3),
                marker=dict(color="orange", symbol="circle", size=5),
                name="Prior FY (same dates)",
                hovertemplate="%{x}<br>%{y:,.0f} Lbs (Prior FY)<extra></extra>",
            )
        )

    # Mark flagged bars (PoP >= 20%)
    if "flag_pop_20" in df_entity.columns and "pop_delta_pct" in df_entity.columns:
        flagged = df_entity[df_entity["flag_pop_20"] == True].copy()
        if len(flagged) > 0:
            fx = [period_label(granularity, k) for k in flagged["period_key"]]
            fy = flagged["lbs"].tolist()

            # pop_delta_pct expected as a proportion (e.g., 0.23). Convert to percent.
            flagged_pct = (flagged["pop_delta_pct"].astype(float) * 100.0).to_numpy()

            fig.add_trace(
                go.Scatter(
                    x=fx,
                    y=fy,
                    mode="markers",
                    name="Flag (±20% vs Prior Period)",
                    marker=dict(size=10, color="red", symbol="circle"),
                    customdata=flagged_pct,
                    hovertemplate="This is %{customdata:.1f}% change vs Prior Period<extra></extra>",
                )
            )

    fig.update_layout(
        height=420,
        margin=dict(l=30, r=20, t=30, b=60),
        xaxis_title="Period",
        yaxis_title="Lbs Distributed",
        legend_title="Series",
    )
    return fig
