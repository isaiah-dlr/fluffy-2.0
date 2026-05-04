# KPI Fulfillment Showcase
# Converted from Streamlit to NiceGUI

from __future__ import annotations
from datetime import date

import pandas as pd
from nicegui import ui

from fsdhelpers import kpi_cleaner, kpi_summaries

# ---------- Data loading ----------
_master_cache: pd.DataFrame | None = None


def get_master() -> pd.DataFrame | None:
    global _master_cache
    if _master_cache is not None:
        return _master_cache
    try:
        _master_cache = kpi_cleaner.load_and_build_master()
        return _master_cache
    except Exception as e:
        return None


VIEW_OPTIONS = [
    "Overall Case Movement",
    "Overall Weight Movement",
    "Overall Pallets",
    "Employee Case Movement",
    "Employee Weight Movement",
    "Employee Pallets",
    "Order Tier Distribution",
    "Pallet Effort Model (Experimental)",
]


def render():
    with ui.column().classes("w-full mx-auto px-4 py-4 gap-6"):
        # Header
        with ui.column().classes("gap-3"):
            ui.label("KPI Fulfillment Showcase").style(
                "font-size: 2.5rem; font-weight: 700; color: var(--q-primary);")

            ui.label(
                "A prototype showcase for analyzing key performance metrics — daily and weekly "
                "case or pallet movement over time. Designed to help operations continuously "
                "identify pain points and improve on them."
            ).style("font-size: 1.25rem; color: var(--q-accent); font-style: italic;")

        master = get_master()
        if master is None:
            ui.label(
                "⚠️ Could not load KPI data. Ensure all three CSV files exist in pages/kpi_data/."
            ).style("color: red; font-weight: 600;")
            return

        master["Shipment Date"] = pd.to_datetime(master["Shipment Date"], errors="coerce")
        valid_dates = master["Shipment Date"].dropna()
        if valid_dates.empty:
            ui.label("⚠️ No valid Shipment Date values found.").style("color: red;")
            return

        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()
        employees = sorted(master["Team Member (Whiteboard)"].dropna().unique().tolist())

        ui.separator()

        # Tabs
        with ui.tabs().classes("w-full big-tabs") as tabs:
            tab_model = ui.tab("KPI Model").classes("big-tabs)")
            tab_method = ui.tab("Parameters & Preparation").classes("big-tabs)")

        with ui.tab_panels(tabs, value=tab_model).classes("w-full"):

            # ---- MODEL TAB ----
            with ui.tab_panel(tab_model):
                with ui.column().classes("w-full gap-4"):
                    ui.label("Model Controls").style(
                        "font-size: 1.2rem; font-weight: 700; color: var(--q-primary);")


                    # --- Analysis Controls ---
                    with ui.grid(columns=2).classes("w-full gap-4 flex-wrap"):
                        with ui.column().classes("gap-1"):
                            ui.label("Select Period Level").classes("section-label")
                            period_select = ui.toggle(
                                options=["Daily","Weekly", "Monthly"],
                                value="Weekly",
                                ).props("unelevated spread").classes("col-span-2 q-btn-toggle")
                        
                        with ui.column().classes("gap-1"):
                            ui.label("Select KPI to Report").classes("section-label")
                            view_select = ui.select(
                                label="Select Analysis",
                                options=VIEW_OPTIONS,
                                value="Overall Case Movement",
                            ).style("min-width: 280px;")
                            
                    # --- Date Range Selection ---
                    with ui.row().classes("w-full gap-4 flex-wrap"):

                        # --- Start Date ---
                        with ui.column().classes("gap-1"):
                            ui.label("Start Date").classes("section-label")
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
                            ui.label("End Date").classes("section-label")
                            with ui.input(value=str(max_date)).classes("w-44 compact-date") as end_date_input:
                                with ui.menu().props("no-parent-event").classes("date-menu") as end_menu:
                                    end_calendar = ui.date(
                                        value=str(max_date),
                                        on_change=lambda e: (
                                            end_date_input.set_value(e.value),
                                            end_menu.close()))
                                end_date_input.on("click", end_menu.open)

                    # --- Employee Filter & Selection ---    
                    with ui.grid(columns=2).classes("w-full gap-4 flex-wrap"):
                        with ui.column().classes("gap-1"):
                            ui.label("Select Report View").style("color: var(--q-primary); font-size: 1.2rem; font-weight: 600;")
                            employee_mode_radio = ui.radio(
                                ["Overall", "By Employee"],
                                value="Overall",
                            ).props("inline").style(f"color: var(--q-secondary); font-size: 1rem; font-weight: 600;")
                        
                        with ui.column().classes("gap-1"):
                            employee_filter = ui.label("Employee Filter (only for By Employee mode)").classes("section-label")

                            employee_select = ui.select(
                                options=employees,
                                multiple=True,
                                with_input=True,
                                value=employees[:1],
                            ).props("dense options-dense use-chips clearable"
                                    ).classes("col-span-2 entity-select")
                            
                                
                    # ---- Employee mode toggle ----
                    def _toggle_employee_mode(e=None):
                        """Show/hide date inputs depending on the selected employee mode.

                        Handles three call signatures:
                        • called with no argument (initial render)              → read widget value directly
                        • called from on_change with a ValueChangeEventArguments → use e.value
                        • called from 'update:model-value' Vue event             → use e.args (may be a list)
                        """
                        if e is None:
                            selected_value = employee_mode_radio.value
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

                        is_range = selected_value == "Overall"

                        # Toggle visibility of the four inputs
                        employee_select.set_visibility(not is_range)
                        employee_filter.set_visibility(not is_range)

                    employee_mode_radio.on("update:model-value", _toggle_employee_mode)
                    _toggle_employee_mode()   # apply correct initial state without relying on an event object

                    ui.separator()

                    chart_container = ui.column().classes("w-full gap-4")
                    table_container = ui.column().classes("w-full")

                    def run_analysis():
                        chart_container.clear()
                        table_container.clear()

                        try:
                            sd = pd.Timestamp(start_date_input.value)
                            ed = pd.Timestamp(end_date_input.value)
                        except Exception:
                            with chart_container:
                                ui.label("⚠️ Invalid date selection.").style("color: red;")
                            return

                        selected_employees = (
                            employee_select.value if employee_mode_radio.value == "By Employee" else None
                        )

                        filtered = kpi_summaries.filter_master(
                            master,
                            start_date=sd,
                            end_date=ed,
                            employees=selected_employees,
                        )

                        period = period_select.value
                        view = view_select.value

                        CHART_VIEWS = {
                            "Overall Case Movement":   lambda: kpi_summaries.overall_cases_summary(filtered, period).set_index("Period"),
                            "Overall Weight Movement": lambda: kpi_summaries.overall_weight_summary(filtered, period).set_index("Period"),
                            "Overall Pallets":         lambda: kpi_summaries.overall_pallet_summary(filtered, period).set_index("Period"),
                        }

                        TABLE_VIEWS = {
                            "Employee Case Movement":  lambda: kpi_summaries.employee_cases_summary(filtered, period),
                            "Employee Weight Movement":lambda: kpi_summaries.employee_weight_summary(filtered, period),
                            "Employee Pallets":        lambda: kpi_summaries.employee_pallet_summary(filtered, period),
                        }

                        try:
                            if view == "Pallet Effort Model (Experimental)":
                                df_result, fig = kpi_summaries.pallet_effort_model(filtered)

                                with chart_container:
                                    ui.plotly(fig).classes("w-full")

                                with table_container:
                                    _render_dataframe(df_result, title="Pallet Effort by Tier & Employee")

                            elif view == "Order Tier Distribution":
                                tier_dist_df = kpi_summaries.order_tier_distribution(filtered)
                                # unpack 4 values now instead of 3
                                summary_df, trend_fig, orders_fig, heatmap_fig = kpi_summaries.order_tier_period_summary(filtered, period)

                                with chart_container:
                                    ui.label(f"Effort Trend — {period}")
                                    ui.plotly(trend_fig).classes("w-full")
                                    ui.label(f"Orders by Tier — {period}")   # ← new
                                    ui.plotly(orders_fig).classes("w-full")             # ← new
                                    ui.label(f"Order Count Heatmap — {period} × Tier")
                                    ui.plotly(heatmap_fig).classes("w-full")

                                with table_container:
                                    _render_dataframe(tier_dist_df, title="Overall Tier Distribution (full date range)")
                                    _render_dataframe(summary_df, title=f"Period × Tier Breakdown ({period})")

                            elif view in CHART_VIEWS:
                                df_result = CHART_VIEWS[view]()

                                with chart_container:
                                    import plotly.express as px

                                    df_plot = df_result.reset_index()
                                    col_y = df_plot.columns[-1]

                                    fig = px.line(
                                        df_plot,
                                        x="Period",
                                        y=col_y,
                                        title=view,
                                        markers=True,
                                    )

                                    fig.update_layout(
                                        height=400,
                                        margin=dict(l=30, r=20, t=40, b=60),
                                        plot_bgcolor="white",
                                    )

                                    fig.update_xaxes(showgrid=True, gridcolor="#eee")
                                    fig.update_yaxes(showgrid=True, gridcolor="#eee")

                                    ui.plotly(fig).classes("w-full")

                            elif view in TABLE_VIEWS:
                                df_result = TABLE_VIEWS[view]()

                                with table_container:
                                    _render_dataframe(df_result, title=view)

                        except Exception as e:
                            with chart_container:
                                ui.label(f"⚠️ Error running analysis: {e}").style("color: red;")

                    ui.button("Run Analysis", on_click=run_analysis).props("unelevated").style(
                        "background: var(--q-primary); color: white; font-weight: 600; border-radius: 8px;"
                    )

                    chart_container
                    table_container

            # ---- METHODOLOGY TAB ----
            with ui.tab_panel(tab_method):
                with ui.column().classes("w-full gap-5"):
                    ui.label("Data Preparation & Cleaning Pipeline").style(
                        "font-size: 1.2rem; font-weight: 700; color: var(--q-primary);"
                    )

                    sections = [
                        ("Source Datasets", [
                            "Order Fulfillment Whiteboard",
                            "Quality Control Log",
                            "Order Gross Weights",
                        ]),
                        ("Key Cleaning Steps — Whiteboard", [
                            "Forward-fill missing dates and agency names",
                            "Remove incomplete order rows",
                        ]),
                        ("Key Cleaning Steps — QC Log", [
                            "Remove blank records",
                            "Forward-fill shipment dates",
                        ]),
                        ("Key Cleaning Steps — Gross Weights", [
                            "Normalize order numbers",
                            "Clean numeric fields",
                            "Remove produce shipments",
                        ]),
                    ]

                    for title, items in sections:
                        with ui.card().classes("w-full").style("border-radius: 10px;"):
                            ui.label(title).style("font-weight: 600; font-size: 1.0rem; color: var(--q-primary);")
                            for item in items:
                                with ui.row().classes("items-center gap-2"):
                                    ui.label("•").style("font-size: 1.0rem; color: var(--q-accent);")
                                    ui.label(item).style("font-size: 1.0rem; color: var(--q-accent);")

                    with ui.card().classes("w-full").style("border-radius: 10px;"):
                        ui.label("Merge Logic").style("font-weight: 600; font-size: 1.0rem; color: var(--q-primary);")
                        ui.label("All datasets are merged using a normalized Order Number key.").style("font-size: 1.0rem; color: var(--q-accent);")

                    with ui.card().classes("w-full").style("border-radius: 10px;"):
                        ui.label("Feature Engineering").style("font-weight: 600; font-size: 1.0rem; color: var(--q-primary);")
                        for item in [
                            "Order Size Tier model (scaled composite index)",
                            "Pallet Effort multiplier model",
                            "Employee productivity metrics",
                        ]:
                            with ui.row().classes("items-center gap-2"):
                                ui.label("•").style("font-size: 1.0rem; color: var(--q-accent);")
                                ui.label(item).style("font-size: 1.0rem; color: var(--q-accent);")

                    ui.separator()
                    ui.label("Cleaned Master Dataset Preview (first 50 rows)").style(
                        "font-weight: 600; color: var(--q-primary); font-size: 1.2rem;"
                    )
                    _render_dataframe(master.head(50))

                    ui.button("Download Master Dataset as Excel", on_click=lambda: ui.download(
                        src=kpi_cleaner.excel_bytes(master),
                        filename="master_dataset.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )).classes('button')


def _render_dataframe(df: pd.DataFrame, title: str = ""):
    if title:
        ui.label(title).style("font-weight: 600; color: var(--q-primary); font-size: 1.2rem;")

    cols = [{"headerName": c, "field": c, "sortable": True, "filter": True} for c in df.columns]
    rows = df.astype(str).to_dict("records")

    ui.aggrid({
        "columnDefs": cols,
        "rowData": rows,
        "defaultColDef": {"resizable": True, "minWidth": 80},
        "pagination": True,
        "paginationPageSize": 20,
    }).classes("w-full").style("height: 420px;")