from nicegui import ui


def render():
    with ui.column().classes("w-full max-w-4xl mx-auto px-6 py-8 gap-6"):
        # Hero
        with ui.row().classes("items-center gap-3"):
            ui.label("🥑").style("font-size: 2.5rem;")
            ui.label("Welcome to Fluffy!").style(
                "font-size: 2rem; font-weight: 700; color: #1a3a5c;"
            )

        ui.label(
            "Fluffy is an all-in-one interface designed specifically for Feeding San Diego."
        ).style("font-size: 1.05rem; color: #444;")

        ui.separator()

        ui.label("What can Fluffy do?").style(
            "font-size: 1.2rem; font-weight: 600; color: #1a3a5c;"
        )

        # Feature cards
        features = [
            (
                "🔍",
                "Ceres6 Query Tool",
                "/ceres6",
                "A user-friendly interface for querying the Ceres6 database — locate specific "
                "fields in reports about food distribution, member organizations, and more. "
                "Primary use case is report-building, with plans to expand post-feedback.",
            ),
            (
                "📈",
                "Member Distribution Trends",
                "/order-trends",
                "Visualize and analyze trends in member or regional distribution over time. "
                "Assists Neighborhood Partnerships with flagging large member orders and taking "
                "corrective action. Download a copy of the report for record-keeping.",
            ),
            (
                "🎯",
                "KPI Fulfillment Showcase",
                "/kpi",
                "A prototype showcase for analyzing key performance metrics — daily and weekly "
                "case or pallet movement over time. Designed to help operations continuously "
                "identify pain points and improve on them.",
            ),
        ]

        with ui.grid(columns=1).classes("w-full gap-4"):
            for icon, title, route, description in features:
                with ui.card().classes("w-full cursor-pointer hover:shadow-lg transition-shadow").style(
                    "border-radius: 12px; border-left: 4px solid #1a3a5c;"
                ) as card:
                    with ui.row().classes("items-start gap-4 p-2"):
                        ui.label(icon).style("font-size: 2rem; min-width: 2.5rem;")
                        with ui.column().classes("gap-1"):
                            ui.label(title).style(
                                "font-size: 1.1rem; font-weight: 600; color: #1a3a5c;"
                            )
                            ui.label(description).style("color: #555; line-height: 1.5;")
                            ui.button(
                                f"Open {title} →",
                                on_click=lambda r=route: ui.navigate.to(r),
                            ).props("flat").style(
                                "color: #1a3a5c; font-weight: 600; padding: 0; margin-top: 4px;"
                            )
