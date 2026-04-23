from __future__ import annotations

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler


EMPLOYEE_COL = "Team Member (Whiteboard)"


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


# -----------------------------
# OVERALL MOVEMENT SUMMARIES
# -----------------------------

def overall_cases_summary(master, period):

    df = add_period_column(master, period)

    return (
        df.groupby("Period", as_index=False)["Case Quantity Pulled"]
        .sum()
        .rename(columns={"Case Quantity Pulled": "Total Cases"})
    )


def overall_weight_summary(master, period):

    df = add_period_column(master, period)

    return (
        df.groupby("Period", as_index=False)["Gross Weight"]
        .sum()
        .rename(columns={"Gross Weight": "Total Weight"})
    )


def overall_pallet_summary(master, period):

    df = add_period_column(master, period)

    return (
        df.groupby("Period", as_index=False)["No. of Pallets"]
        .sum()
        .rename(columns={"No. of Pallets": "Total Pallets"})
    )


# -----------------------------
# EMPLOYEE SUMMARIES
# -----------------------------

def employee_cases_summary(master, period):

    df = add_period_column(master, period)

    return (
        df.groupby([EMPLOYEE_COL, "Period"], as_index=False)["Case Quantity Pulled"]
        .sum()
        .rename(columns={"Case Quantity Pulled": "Total Cases"})
    )


def employee_weight_summary(master, period):

    df = add_period_column(master, period)

    return (
        df.groupby([EMPLOYEE_COL, "Period"], as_index=False)["Gross Weight"]
        .sum()
        .rename(columns={"Gross Weight": "Total Weight"})
    )


def employee_pallet_summary(master, period):

    df = add_period_column(master, period)

    return (
        df.groupby([EMPLOYEE_COL, "Period"], as_index=False)["No. of Pallets"]
        .sum()
        .rename(columns={"No. of Pallets": "Total Pallets"})
    )


# -----------------------------
# ORDER TIER MODEL
# -----------------------------

def build_order_level(master):

    df = master.copy()

    df = df[df["Product Type"].isin(["Dry", "Frozen", "Cooler"])]

    order_level = df.groupby("Order Number", as_index=False).agg(
        Agency_Name=("Agency Name", "first"),
        Pallets=("No. of Pallets", "sum"),
        Gross_Weight=("Gross Weight", "max"),
        Cases_Ordered=("Total Cases Ordered", "max"),
        Employee=("Team Member (Whiteboard)", "first"),
    )

    scaler = MinMaxScaler()

    order_level[
        ["Cases_Scaled", "Pallets_Scaled", "Weight_Scaled"]
    ] = scaler.fit_transform(
        order_level[["Cases_Ordered", "Pallets", "Gross_Weight"]]
    )

    order_level["Weighted_Size_Index"] = (
        order_level["Cases_Scaled"] * 0.70
        + order_level["Pallets_Scaled"] * 0.10
        + order_level["Weight_Scaled"] * 0.20
    )

    order_level["Order_Tier"] = pd.qcut(
        order_level["Weighted_Size_Index"],
        q=5,
        labels=["Extra Small", "Small", "Medium", "Large", "Extra Large"]
    )

    return order_level


def order_tier_distribution(master):

    order_level = build_order_level(master)

    return (
        order_level.groupby("Order_Tier", as_index=False)
        .agg(
            Orders=("Order Number", "count"),
            Total_Pallets=("Pallets", "sum"),
            Total_Weight=("Gross_Weight", "sum")
        )
        .sort_values("Orders", ascending=False)
    )


# -----------------------------
# PALLET EFFORT MODEL
# -----------------------------

def pallet_effort_model(master):

    df = master.copy()

    tier_mult = {
        "Extra Small": 1.00,
        "Small": 1.25,
        "Medium": 1.75,
        "Large": 1.50,
        "Extra Large": 1.25
    }

    order_level = build_order_level(df)

    df = df.merge(
        order_level[["Order Number", "Order_Tier"]],
        on="Order Number",
        how="left"
    )

    df["Effort Multiplier"] = df["Order_Tier"].map(tier_mult)

    df["Pallet Effort"] = df["No. of Pallets"] * df["Effort Multiplier"]

    effort = (
        df.groupby(["Team Member (QC Log)", "Shipment Date"])
        .agg(
            Total_Pallets=("No. of Pallets", "sum"),
            Total_Effort=("Pallet Effort", "sum")
        )
        .reset_index()
    )

    return effort