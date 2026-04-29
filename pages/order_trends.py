# Member Distribution Trends
# Converted from Streamlit to NiceGUI

from __future__ import annotations
from datetime import date

import io
import numpy as np
import pandas as pd
from nicegui import ui

from fsdhelpers import config
from fsdhelpers.data_prep import add_derived_fields, load_dataset, resolve_window
from fsdhelpers.aggregations import (
    filter_base, agg_entity_period, agg_entity_range, add_deltas,
    build_prior_fy_aligned, add_prior_and_did,
)
from fsdhelpers.charts import make_entity_chart, period_label
from fsdhelpers.narrative import build_narrative
from fsdhelpers.report import build_report_html


# ---------- Helpers ----------
def _format_pct(x) -> str:
    if pd.isna(x):
        return ""
    if x == float("inf"):
        return "∞"
    if x == float("-inf"):
        return "-∞"
    try:
        return f"{x*100:.1f}%"
    except Exception:
        return ""


def _period_label(granularity: str, period_key: pd.Timestamp) -> str:
    return period_label(granularity, period_key)


# ---------- Data loading ----------
_df_raw_cache = None
_df_cache = None


def get_df():
    global _df_raw_cache, _df_cache
    if _df_cache is not None:
        return _df_cache, None
    try:
        df_raw = load_dataset(str(config.DATA_PATH))
        df = add_derived_fields(df_raw)

        PT_COL = "FBC Product Type Code"
        pt_num = pd.to_numeric(df[PT_COL], errors="coerce")
        NONFOOD_CODES = {1, 2, 12, 13, 19, 20, 22}
        PRODUCE_CODES = {28}
        conditions = [pt_num.isin(PRODUCE_CODES), pt_num.isin(NONFOOD_CODES)]
        choices = ["Produce", "Non-Food"]
        df["_product_type_bucket"] = np.select(conditions, choices, default="Non-Produce")
        _df_cache = df
        return df, None
    except Exception as e:
        return None, str(e)

# ---------- NiceGUI render ----------
def render():
    with ui.column().classes("w-full mx-auto px-4 py-4 gap-6"):
        with ui.column().classes("gap-3"):
            ui.label("Member Distribution Trends Calculator").style(
                "font-size: 2.5rem; font-weight: 700; color: var(--q-primary);")

            ui.label(
            "Calculate trends in member or regional distribution over time, with optional "
            "prior fiscal year comparison. Download a copy of the report for further analysis.").style(
                "color: var(--q-secondary); font-size: 1.25rem; font-style: italic;")

        df, err = get_df()
        if err or df is None:
            ui.label(f"⚠️ Failed to load data: {err}").style("color: red; font-weight: 600;")
            return

        ui.separator()

        INV_COL = "Inventory Posting Group"
        DOC_COL = "Document Type"

        inv_canonical = ["Donated", "Purchased", "USDA/Government"]
        inv_present = [x for x in inv_canonical if x in df[INV_COL].dropna().astype(str).unique()]

        doc_canonical = ["Agency Invoice", "Agency Credit Memo", "Agency Shipment", "Agency Return Receipt", "Other"]
        doc_raw = df[DOC_COL].astype(str)
        known_docs = set(doc_canonical[:-1])
        df["_doc_bucket"] = doc_raw.where(doc_raw.isin(known_docs), other="Other")
        df.loc[df[DOC_COL].isna(), "_doc_bucket"] = None
        doc_present = [x for x in doc_canonical if x in df["_doc_bucket"].dropna().unique()]

        min_date = pd.to_datetime(df["date"].min()).date()
        max_date = pd.to_datetime(df["date"].max()).date()

        # ---- CONTROLS ----
        ui.label("Report Location Type").style(
            f"font-size: 1.2rem; font-weight: 600; color: var(--q-primary);"
        )

        entity_values_agency = sorted(df["entity_agency"].dropna().astype(str).unique().tolist())
        entity_values_region = sorted(df["entity_region"].dropna().astype(str).unique().tolist())
        
        def _update_entity_options(mode_val):
            if mode_val == "Agency":
                entity_select.set_options(
                    entity_values_agency,
                    value = entity_values_agency[:1])
            else:
                entity_select.set_options(
                    entity_values_region,
                    value = entity_values_region[:1]
                )
            
        with ui.grid(columns=3).classes("w-full gap-4"):
            mode_radio = ui.radio(
                ["Agency", "Region"], value="Agency", 
                on_change=lambda e: _update_entity_options(e.value)
            ).props("inline").style(
                f"color: var(--q-secondary); font-size: 1rem; font-weight: 600;")   

            entity_select = ui.select(
                label="Selected Agency/Region(s)",
                options=entity_values_agency,
                multiple=True,
                with_input=True,
                value=entity_values_agency[:1],
            ).props("dense options-dense use-chips clearable"
                    ).classes("col-span-2 entity-select")

        with ui.grid(columns=2).classes("w-full gap-4 flex-wrap"):
            ui.label("Reporting Cycle").style(
            f"font-size: 1.2rem; font-weight: 600; color: var(--q-primary);").classes("col-span-2")
            granularity_select = ui.toggle(
                ["Weekly", "Monthly", "Yearly"],
                value="Weekly",
            ).props("unelevated spread").classes("col-span-2 q-btn-toggle")

            inv_select = ui.select(
                label="Inventory Posting Group",
                options=inv_present,
                multiple=True,
                with_input=True,
                value=inv_present,
            ).props("dense options-dense use-chips clearable"
                ).classes("col-span-2 entity-select")

            doc_select = ui.select(
                label="Document Type",
                options=doc_present,
                multiple=True,
                with_input=True,
                value=doc_present,
            ).props("dense options-dense use-chips clearable"
                ).classes("col-span-2 entity-select")

            product_type_select = ui.select(
                label="Product Type",
                options=["Produce", "Non-Produce", "Non-Food"],
                multiple=True,
                with_input=True,
                value=["Produce", "Non-Produce", "Non-Food"],
            ).props("dense options-dense use-chips clearable"
                ).classes("col-span-2 entity-select")
            
        ui.separator()
        ui.label("Time Window").style(
            f"font-size: 1.2rem; font-weight: 600; color: var(--q-primary);"
        )

        window_mode_radio = ui.radio(
            ["Date Range", "Anchor + Period Lookback"], value="Date Range"
        ).props("inline").style(f"margin-bottom: 1rem; color: var(--q-secondary); font-size: 1rem; font-weight: 600;")
        
        with ui.row().classes("w-full gap-4 flex-wrap items-end"):

            # --- Start Date ---
            with ui.column().classes("gap-1"):
                ui.label("Start Date").classes("text-sm font-medium text-gray-600")
                with ui.input(value=str(min_date)).classes("w-44 compact-date") as start_date_input:
                    with ui.menu().props("no-parent-event").classes("date-menu") as start_menu:
                        start_calendar = ui.date(
                            value=str(min_date),
                            on_change=lambda e: (
                                start_date_input.set_value(e.value),
                                start_menu.close()
                            )
                        )
                    start_date_input.on("click", start_menu.open)

            # --- End Date ---
            with ui.column().classes("gap-1"):
                ui.label("End Date").classes("text-sm font-medium text-gray-600")
                with ui.input(value=str(max_date)).classes("w-44 compact-date") as end_date_input:
                    with ui.menu().props("no-parent-event").classes("date-menu") as end_menu:
                        end_calendar = ui.date(
                            value=str(max_date),
                            on_change=lambda e: (
                                end_date_input.set_value(e.value),
                                end_menu.close()
                            )
                        )
                    end_date_input.on("click", end_menu.open)

            # --- Anchor Date ---
            with ui.column().classes("gap-1") as anchor_date_col:
                ui.label("Anchor Date").classes("text-sm font-medium text-gray-600")
                with ui.input(value=str(max_date), placeholder="2020-10-01").classes("w-44 compact-date") as anchor_date_input:
                    with ui.menu().props("no-parent-event").classes("date-menu") as anchor_menu:
                        anchor_calendar = ui.date(
                            value=str(max_date),
                            on_change=lambda e: (
                                anchor_date_input.set_value(e.value),
                                anchor_menu.close()
                            )
                        )
                    anchor_date_input.on("click", anchor_menu.open)

            # --- Lookback periods (hidden initially) ---
            lookback_input = ui.number(
                "Periods to Look Back",
                value=3,
                min=0,
                max=52,
                step=1,
            ).classes("w-52")

        yoy_toggle = ui.checkbox("Include prior fiscal year same-dates?", value=False).style(
            f"color: var(--q-secondary); margin-top: 0.5rem; font-size: 1rem; font-weight: 600;"
        )

        # ---- Window mode toggle ----
        def _toggle_window_mode(e=None):
            """Show/hide date inputs depending on the selected window mode.

            Handles three call signatures:
              • called with no argument (initial render)              → read widget value directly
              • called from on_change with a ValueChangeEventArguments → use e.value
              • called from 'update:model-value' Vue event             → use e.args (may be a list)
            """
            if e is None:
                selected_value = window_mode_radio.value
            elif hasattr(e, "value"):
                # ValueChangeEventArguments (NiceGUI on_change)
                selected_value = e.value
            elif hasattr(e, "args"):
                # GenericEventArguments from a raw Vue event binding.
                # e.args can be the bare string OR a list like [new_val, old_val].
                raw = e.args
                selected_value = raw[0] if isinstance(raw, (list, tuple)) else raw
            else:
                selected_value = str(e)

            is_range = selected_value == "Date Range"

            # Toggle visibility of the four inputs
            start_date_input.set_visibility(is_range)
            end_date_input.set_visibility(is_range)
            anchor_date_input.set_visibility(not is_range)
            lookback_input.set_visibility(not is_range)

        window_mode_radio.on("update:model-value", _toggle_window_mode)
        _toggle_window_mode()   # apply correct initial state without relying on an event object

        ui.separator()

        output_container = ui.column().classes("w-full gap-6")

        def run_report():
            output_container.clear()

            selected_entities = list(entity_select.value or [])
            if not selected_entities:
                with output_container:
                    ui.label("⚠️ Select at least one Agency/Region.").style("color: red;")
                return

            granularity = granularity_select.value or "Weekly"
            mode = mode_radio.value
            window_mode = window_mode_radio.value

            # Re-apply filters on a fresh copy
            dff = df.copy()
            if inv_select.value:
                dff = dff[dff[INV_COL].astype(str).isin(set(inv_select.value))]
            if doc_select.value:
                dff = dff[dff["_doc_bucket"].astype(str).isin(set(doc_select.value))]
            if product_type_select.value:
                dff = dff[dff["_product_type_bucket"].isin(product_type_select.value)]

            try:
                if window_mode == "Date Range":
                    window = resolve_window(
                        dff, granularity=granularity, mode=mode,
                        start_date=pd.Timestamp(start_date_input.value),
                        end_date=pd.Timestamp(end_date_input.value),
                    )
                else:
                    # lookback_input.value is a float from ui.number — convert safely
                    raw_lookback = lookback_input.value
                    lookback_periods = int(raw_lookback) if raw_lookback is not None else 3

                    window = resolve_window(
                        dff, granularity=granularity, mode=mode,
                        anchor_date=pd.Timestamp(anchor_date_input.value),
                        lookback_periods=lookback_periods,
                    )
            except Exception as e:
                with output_container:
                    ui.label(f"⚠️ Window error: {e}").style("color: red;")
                return

            try:
                base = filter_base(dff, mode=mode, selected_entities=selected_entities, window=window, granularity=granularity)
                if len(base) == 0:
                    with output_container:
                        ui.label("⚠️ No rows match the selected filters and date window.").style("color: orange;")
                    return

                ep = agg_entity_period(base)
                er = agg_entity_range(base, period_keys=window.period_keys)
                epd = add_deltas(ep, er)

                include_prior = bool(yoy_toggle.value) and granularity in ("Weekly", "Monthly")
                if include_prior:
                    prior = build_prior_fy_aligned(dff, mode=mode, selected_entities=selected_entities, window=window, granularity=granularity)
                    epd = add_prior_and_did(epd, prior)

                epd = epd.merge(
                    er[["entity_id", "hh_median_range", "hh_median_range_bucket", "hh_max_range", "hh_max_range_bucket"]],
                    on="entity_id", how="left",
                )

                epd["period_label"] = epd["period_key"].apply(lambda k: _period_label(granularity, k))
                epd["Flag"] = epd["flag_pop_20"].apply(lambda b: "****" if b else "")

                y1_cols = ["entity_id", "period_label", "lbs", "hh_median", "hh_median_bucket",
                           "hh_max", "hh_max_bucket", "hh_median_range", "hh_median_range_bucket",
                           "hh_max_range", "hh_max_range_bucket", "pop_delta_lbs", "pop_delta_pct",
                           "rng_delta_lbs", "rng_delta_pct", "Flag"]
                if include_prior:
                    y1_cols += ["lbs_prior", "pop_delta_pct_prior", "rng_delta_pct_prior", "did_pop_pct", "did_rng_pct"]

                y1 = epd[[c for c in y1_cols if c in epd.columns]].copy()
                y1_disp = y1.copy()

                for c in ["lbs", "pop_delta_lbs", "rng_delta_lbs", "lbs_prior"]:
                    if c in y1_disp.columns:
                        y1_disp[c] = y1_disp[c].apply(lambda x: "" if pd.isna(x) else f"{float(x):,.0f}")

                for c in ["hh_median", "hh_max", "hh_median_range", "hh_max_range"]:
                    if c in y1_disp.columns:
                        y1_disp[c] = y1_disp[c].apply(lambda x: "" if pd.isna(x) else f"{float(x):,.0f}")

                for c in ["pop_delta_pct", "rng_delta_pct", "pop_delta_pct_prior", "rng_delta_pct_prior", "did_pop_pct", "did_rng_pct"]:
                    if c in y1_disp.columns:
                        y1_disp[c] = y1_disp[c].apply(_format_pct)

                bucket_cols = ["hh_median_bucket", "hh_max_bucket", "hh_median_range_bucket", "hh_max_range_bucket",
                               "Median Households (Range)", "Max Households (Range)"]
                y1_disp = y1_disp.drop(columns=[c for c in bucket_cols if c in y1_disp.columns])

                rename_map = {
                    "entity_id": "Entity",
                    "period_label": "Period",
                    "Flag": "Alert",
                    "lbs": "Total Pounds",
                    "pop_delta_lbs": "Δ Lbs vs Prior Period",
                    "pop_delta_pct": "% Chg vs Prior Period",
                    "rng_delta_lbs": "Δ Lbs vs Range Avg",
                    "rng_delta_pct": "% Chg vs Range Avg",
                    "hh_median": "Median HH Size",
                    "hh_max": "Max HH Size",
                    "hh_median_range": "Median HH (Range)",
                    "hh_max_range": "Max HH (Range)",
                }
                
                if include_prior:
                    rename_map |= {
                        "lbs_prior": "Total Lbs (Prior FY)",
                        "pop_delta_pct_prior": "% Chg vs Prior (Prior FY)",
                        "rng_delta_pct_prior": "% Chg vs Range (Prior FY)",
                        "did_pop_pct": "DiD % vs Prior FY (Period)",
                        "did_rng_pct": "DiD % vs Prior FY (Range)",
                    }
                y1_disp = y1_disp.rename(columns=rename_map)

                base_display_cols = [
                    "Entity",
                    "Period",
                    "Alert",
                    "Total Pounds",
                    "Δ Lbs vs Prior Period",
                    "% Chg vs Prior Period",
                    "Δ Lbs vs Range Avg",
                    "% Chg vs Range Avg",
                ]

                advanced_display_cols = [
                    "Median HH Size",
                    "Max HH Size",
                    "Median HH (Range)",
                    "Max HH (Range)",
                ]

                if include_prior:
                    advanced_display_cols += [
                        "Total Lbs (Prior FY)",
                        "% Chg vs Prior (Prior FY)",
                        "% Chg vs Range (Prior FY)",
                        "DiD % vs Prior FY (Period)",
                        "DiD % vs Prior FY (Range)",
                    ]

                final_display_cols = base_display_cols + advanced_display_cols

                y1_disp = y1_disp[
                    [c for c in final_display_cols if c in y1_disp.columns]
                ]

                with output_container:
                    # 1. Summary Table
                    ui.label("1. Summary Table").classes("order-trend-output")
                    ui.label("Alert (****) triggers on a ±20% change vs the immediate previous period.").classes("order-trend-label")
                    
                    advanced_details = ui.checkbox(
                        "Show advanced details",
                        value=False,).style("color: var(--q-secondary); font-size: 1rem; font-weight: 600;")
                    
                    hidden_by_default_cols = [
                        "Median HH Size",
                        "Max HH Size",
                        "Median HH (Range)",
                        "Max HH (Range)",
                        "Δ Lbs vs Range Avg",
                        "% Chg vs Range Avg",
                    ]

                    rows = y1_disp.to_dict("records")

                    def build_column_defs(show_advanced: bool):
                        visible_cols = []

                        for c in y1_disp.columns:
                            if not show_advanced and c in hidden_by_default_cols:
                                continue

                            visible_cols.append({
                                "headerName": c,
                                "field": c,
                                "sortable": True,
                                "filter": True,
                            })

                        return visible_cols

                    grid = ui.aggrid({
                        "columnDefs": build_column_defs(False),
                        "rowData": rows,
                        "defaultColDef": {
                            "resizable": True,
                            "minWidth": 90,
                        },
                        "pagination": True,
                        "paginationPageSize": 20,
                    }).classes("w-full").style("height: 400px;")

                    def toggle_advanced_details(e):
                        grid.options["columnDefs"] = build_column_defs(bool(e.value))
                        grid.update()

                    advanced_details.on_value_change(toggle_advanced_details)

                    ui.separator()

                    # 2. Charts
                    ui.label("2. Trend Figures by Agency/Region").classes("order-trend-output")
                    chart_html_frags = []
                    for entity_id, g in epd.groupby("entity_id"):
                        ui.label(str(entity_id)).classes("order-trend-label")
                        fig = make_entity_chart(g, granularity=granularity, include_prior=include_prior)
                        ui.plotly(fig).classes("w-full")
                        chart_html_frags.append(fig.to_html(full_html=False, include_plotlyjs="cdn"))

                    ui.separator()

                    # 3. Narrative
                    ui.label("3. Executive Summary").classes("order-trend-output")                    
                    narrative = ""

                    if len(epd):
                        narrative = build_narrative(
                            epd,
                            granularity=granularity,
                            include_prior=include_prior,
                        )

                        narrative_lines = narrative.splitlines()

                        with ui.column().classes("w-full gap-2 narrative-output"):
                            for line in narrative_lines:
                                clean_line = line.strip()

                                if not clean_line:
                                    ui.separator().classes("my-2")
                                    continue

                                # Entity heading line
                                if not clean_line.startswith("-"):
                                    ui.label(clean_line).classes("narrative-heading")
                                
                                # Bullet lines
                                else:
                                    ui.label(clean_line).classes("narrative-bullet")

                    else:
                        ui.label("No data available.").style("color: #888;")
                        
                    ui.separator()

                    # 4. Download
                    ui.label("4. Downloadable HTML Report").classes('order-trend-output')
                    inputs_summary = {
                        "Report Level": mode,
                        "Selected Entities": ", ".join(selected_entities),
                        "Granularity": granularity,
                        "Window Start": str(window.start_date.date()),
                        "Window End": str(window.end_date.date()),
                        "YoY Comparison": "Included" if include_prior else "Not Included",
                    }
                    html_report = build_report_html(
                        inputs_summary=inputs_summary,
                        y1_table=y1_disp,
                        chart_html_fragments=chart_html_frags,
                        narrative_text=narrative,
                        title="Distribution Summary Report",
                    )

                    ui.button("Download HTML Report", on_click=lambda:
                              ui.download(
                                html_report.encode("utf-8"),
                                filename="distribution_report.html",
                                media_type="text/html",)).classes('button')

            except Exception as e:
                with output_container:
                    ui.label(f"⚠️ Error generating report: {e}").style("color: red;")

        ui.button("Generate Report", on_click=run_report).props("unelevated").classes('button')

        output_container
