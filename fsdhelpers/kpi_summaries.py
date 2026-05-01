from __future__ import annotations

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler


EMPLOYEE_COL = "Team Member (Whiteboard)"
WORKDAY_HOURS = 7.0

TIER_ORDER = ["Extra Small", "Small", "Medium", "Large", "Extra Large"]
TIER_ABBREV = {
    "Extra Small": "XS",
    "Small": "S",
    "Medium": "M",
    "Large": "L",
    "Extra Large": "XL",
}

# -----------------------------
# FILTERING + PERIOD HANDLING
# -----------------------------

def filter_master(master, start_date=None, end_date=None, employees=None):
    df = master.copy()
    df["Shipment Date"] = pd.to_datetime(df["Shipment Date"], errors="coerce")

    if start_date:
        df = df[df["Shipment Date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["Shipment Date"] <= pd.Timestamp(end_date)]
    if employees:
        df = df[df[EMPLOYEE_COL].isin(employees)]

    return df


def add_period_column(df, period="Daily"):
    df = df.copy()
    if period == "Daily":
        df["Period"] = df["Shipment Date"].dt.date
    elif period == "Weekly":
        df["Period"] = df["Shipment Date"].dt.to_period("W-MON").apply(lambda r: r.start_time)
    elif period == "Monthly":
        df["Period"] = df["Shipment Date"].dt.to_period("M").apply(lambda r: r.start_time)
    return df


def _dedup_to_order_level(df: pd.DataFrame) -> pd.DataFrame:
    """
    The master dataset is at QC line-item granularity — one row per item
    audited within an order. Columns like No. of Pallets, Case Quantity Pulled,
    and Gross Weight are repeated on every line for the same order. We must
    deduplicate to the order level before summing any of these fields, otherwise
    every metric is inflated by the number of line items per order.
    """
    return df.drop_duplicates(subset=["Order Number", EMPLOYEE_COL, "Shipment Date"])


# -----------------------------
# OVERALL MOVEMENT SUMMARIES
# -----------------------------

def overall_cases_summary(master, period):
    df = _dedup_to_order_level(master)
    df = add_period_column(df, period)
    return (
        df.groupby("Period", as_index=False)["Case Quantity Pulled"]
        .sum()
        .rename(columns={"Case Quantity Pulled": "Total Cases"})
    )


def overall_weight_summary(master, period):
    df = _dedup_to_order_level(master)
    df = add_period_column(df, period)
    return (
        df.groupby("Period", as_index=False)["Gross Weight"]
        .sum()
        .rename(columns={"Gross Weight": "Total Weight"})
    )


def overall_pallet_summary(master, period):
    df = _dedup_to_order_level(master)
    df = add_period_column(df, period)
    return (
        df.groupby("Period", as_index=False)["No. of Pallets"]
        .sum()
        .rename(columns={"No. of Pallets": "Total Pallets"})
    )


# -----------------------------
# EMPLOYEE SUMMARIES
# -----------------------------

def employee_cases_summary(master, period):
    df = _dedup_to_order_level(master)
    df = add_period_column(df, period)
    return (
        df.groupby([EMPLOYEE_COL, "Period"], as_index=False)["Case Quantity Pulled"]
        .sum()
        .rename(columns={"Case Quantity Pulled": "Total Cases"})
    )


def employee_weight_summary(master, period):
    df = _dedup_to_order_level(master)
    df = add_period_column(df, period)
    return (
        df.groupby([EMPLOYEE_COL, "Period"], as_index=False)["Gross Weight"]
        .sum()
        .rename(columns={"Gross Weight": "Total Weight"})
    )


def employee_pallet_summary(master, period):
    df = _dedup_to_order_level(master)
    df = add_period_column(df, period)
    return (
        df.groupby([EMPLOYEE_COL, "Period"], as_index=False)["No. of Pallets"]
        .sum()
        .rename(columns={"No. of Pallets": "Total Pallets"})
    )


# -----------------------------
# ORDER TIER MODEL
# -----------------------------

def build_order_level(master):
    """
    Collapse master (QC line-item level) to one row per Order Number.
    - Pallets: sum across product type rows within the order
    - Gross Weight: first (already rolled up per order in the cleaner)
    - Cases Ordered: max (header-level value, same on every row)
    """
    df = master.copy()
    df = df[df["Product Type"].isin(["Dry", "Frozen", "Cooler"])]

    order_level = df.groupby("Order Number", as_index=False).agg(
        Agency_Name=(       "Agency Name",              "first"),
        Shipment_Date=(     "Shipment Date",            "first"),
        Pallets=(           "No. of Pallets",           "sum"),
        Gross_Weight=(      "Gross Weight",             "first"),   # FIX: was .max()
        Cases_Ordered=(     "Total Cases Ordered",      "max"),
        Employee=(          EMPLOYEE_COL,               "first"),
    )

    scaler = MinMaxScaler()
    order_level[["Cases_Scaled", "Pallets_Scaled", "Weight_Scaled"]] = scaler.fit_transform(
        order_level[["Cases_Ordered", "Pallets", "Gross_Weight"]]
    )

    order_level["Weighted_Size_Index"] = (
        order_level["Cases_Scaled"]  * 0.70
        + order_level["Pallets_Scaled"] * 0.10
        + order_level["Weight_Scaled"]  * 0.20
    )

    order_level["Order_Tier"] = pd.qcut(
        order_level["Weighted_Size_Index"],
        q=5,
        labels=TIER_ORDER,
        duplicates="drop",
    )

    return order_level


def order_tier_distribution(master):
    order_level = build_order_level(master)
    return (
        order_level.groupby("Order_Tier", as_index=False)
        .agg(
            Orders=(       "Order Number", "count"),
            Total_Pallets=("Pallets",      "sum"),
            Total_Weight=( "Gross_Weight", "sum"),
        )
        .sort_values("Orders", ascending=False)
    )


# -----------------------------
# PALLET EFFORT MODEL
# -----------------------------

TIER_MULT = {
    "Extra Small": 1.00,
    "Small":       1.25,
    "Medium":      1.75,
    "Large":       1.50,
    "Extra Large": 1.25,
}


def pallet_effort_model(master) -> tuple[pd.DataFrame, object]:
    """
    Returns (table_df, plotly_fig).

    table_df columns (one row per employee × shipment date):
        Employee, Shipment Date,
        for each tier T in [XS, S, M, L, XL]:
            Total_Pallets_T  – raw pallet count for that tier
            Effort_T         – pallets × multiplier for that tier
        Total_Pallets        – grand total across all tiers
        Total_Effort         – grand total effort across all tiers
        for each tier T:
            Rate_T           – estimated pallets-per-hour for that tier
                               = (tier_pallets / WORKDAY_HOURS) * (tier_effort / total_effort)
                               i.e. the share of the workday attributable to that tier,
                               converted to a pallet-per-hour rate for that tier size.
    """
    import plotly.express as px

    df = master.copy()
    order_level = build_order_level(df)

    # Join tier onto the order-deduplicated view
    # Use the Whiteboard employee (the puller), not QC Log (the auditor)
    df_orders = _dedup_to_order_level(df)
    df_orders = df_orders.merge(
        order_level[["Order Number", "Order_Tier"]],
        on="Order Number",
        how="left",
    )

    df_orders["Order_Tier"] = df_orders["Order_Tier"].astype(str)
    df_orders["Effort_Multiplier"] = df_orders["Order_Tier"].map(TIER_MULT)
    df_orders["Pallet_Effort"] = df_orders["No. of Pallets"] * df_orders["Effort_Multiplier"]

    group_keys = [EMPLOYEE_COL, "Shipment Date", "Order_Tier"]

    tier_df = (
        df_orders.groupby(group_keys, as_index=False)
        .agg(
            Tier_Pallets=("No. of Pallets", "sum"),
            Tier_Effort=( "Pallet_Effort",  "sum"),
        )
    )

    # Pivot so each tier becomes its own columns
    pallet_pivot = tier_df.pivot_table(
        index=[EMPLOYEE_COL, "Shipment Date"],
        columns="Order_Tier",
        values="Tier_Pallets",
        aggfunc="sum",
        fill_value=0,
    )
    effort_pivot = tier_df.pivot_table(
        index=[EMPLOYEE_COL, "Shipment Date"],
        columns="Order_Tier",
        values="Tier_Effort",
        aggfunc="sum",
        fill_value=0,
    )

    # Rename pivot columns
    present_tiers = [t for t in TIER_ORDER if t in pallet_pivot.columns]
    pallet_pivot.columns = [f"Total_Pallets_{TIER_ABBREV[t]}" for t in present_tiers]
    effort_pivot.columns = [f"Effort_{TIER_ABBREV[t]}"        for t in present_tiers]

    result = pallet_pivot.join(effort_pivot).reset_index()

    pallet_cols = [f"Total_Pallets_{TIER_ABBREV[t]}" for t in present_tiers]
    effort_cols = [f"Effort_{TIER_ABBREV[t]}"        for t in present_tiers]

    result["Total_Pallets"] = result[pallet_cols].sum(axis=1)
    result["Total_Effort"]  = result[effort_cols].sum(axis=1)

    # Rate per tier:
    #   effort share of that tier = Effort_T / Total_Effort
    #   hours attributed to that tier = effort_share * WORKDAY_HOURS
    #   pallets per hour for that tier = Total_Pallets_T / hours_attributed
    for t in present_tiers:
        abbr = TIER_ABBREV[t]
        effort_share = result[f"Effort_{abbr}"] / result["Total_Effort"].replace(0, np.nan)
        hours_for_tier = effort_share * WORKDAY_HOURS
        result[f"Rate_{abbr}"] = (
            result[f"Total_Pallets_{abbr}"] / hours_for_tier.replace(0, np.nan)
        ).round(3)

    result["Shipment Date"] = result["Shipment Date"].dt.date
    result = result.rename(columns={EMPLOYEE_COL: "Employee"})

    # --- Build Plotly figure ---
    # Melt rate columns for a grouped bar chart (rate per tier, faceted by employee)
    rate_cols = [f"Rate_{TIER_ABBREV[t]}" for t in present_tiers]
    rate_melt = result.melt(
        id_vars=["Employee", "Shipment Date"],
        value_vars=rate_cols,
        var_name="Tier",
        value_name="Pallets per Hour",
    )
    rate_melt["Tier"] = rate_melt["Tier"].str.replace("Rate_", "", regex=False)

    # Average rate per employee × tier across the date range for the summary chart
    rate_summary = (
        rate_melt.groupby(["Employee", "Tier"], as_index=False)["Pallets per Hour"]
        .mean()
        .dropna(subset=["Pallets per Hour"])
    )
    rate_summary["Tier"] = pd.Categorical(
        rate_summary["Tier"],
        categories=[TIER_ABBREV[t] for t in TIER_ORDER],
        ordered=True,
    )
    rate_summary = rate_summary.sort_values(["Employee", "Tier"])

    fig = px.bar(
        rate_summary,
        x="Tier",
        y="Pallets per Hour",
        color="Employee",
        barmode="group",
        title="Estimated Pallet Build Rate by Tier & Employee (avg pallets / hr)",
        labels={"Pallets per Hour": "Avg Pallets / Hr", "Tier": "Order Tier"},
        category_orders={"Tier": [TIER_ABBREV[t] for t in TIER_ORDER]},
    )
    fig.update_layout(
        height=420,
        margin=dict(l=40, r=20, t=50, b=60),
        plot_bgcolor="white",
        legend_title_text="Employee",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#eee")

    # Column order for table display
    ordered_cols = ["Employee", "Shipment Date"]
    for t in present_tiers:
        abbr = TIER_ABBREV[t]
        ordered_cols += [f"Total_Pallets_{abbr}", f"Effort_{abbr}", f"Rate_{abbr}"]
    ordered_cols += ["Total_Pallets", "Total_Effort"]
    ordered_cols = [c for c in ordered_cols if c in result.columns]

    return result[ordered_cols], fig
