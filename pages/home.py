from nicegui import ui


def render():
    with ui.column().classes("w-full mx-auto px-4 py-4 gap-6"):
        # Hero
        with ui.column().classes("gap-3"):
            ui.label("Welcome to Fluffy!").style(
                "font-size: 2.5rem; font-weight: 700; color: var(--q-primary);")

            ui.label(
            "Fluffy is an all-in-one reporting interface designed specifically for Feeding San Diego.").style(
                "font-size: 1.25rem; font-weight: 600; color: var(--q-secondary); font-style: italic;")

        ui.separator()

        ui.label("What can Fluffy currently do?").style(
            "font-size: 1.5rem; font-weight: 600; color: var(--q-primary);"
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

        with ui.grid(columns=3).classes("w-full gap-4"):
            for icon, title, route, description in features:
                with ui.card().classes("w-full cursor-pointer hover:shadow-lg transition-shadow").style(
                    "padding: 1rem; border-radius: 8px; border-left: 4px solid var(--q-primary);"
                ) as card:
                    with ui.row().classes("items-start gap-4 p-2"):
                        ui.label(icon).style(
                            "font-size: 2rem; min-width: 2.5rem;")
                        with ui.column().classes("gap-1"):
                            ui.label(title).style(
                                "font-size: 1.2rem; font-weight: 600; color: var(--q-secondary);")
                            ui.label(description).style(
                                "font-size: 0.90rem; font-weight: 500; color: var(--q-primary); line-height: 1.5;")
                            ui.button(
                                f"Open {title} →",
                                on_click=lambda r=route: ui.navigate.to(r),
                            ).props("flat").style(
                                "color: var(--q-primary); font-weight: 600; padding: 1rem; margin-top: 4px;"
                            )
