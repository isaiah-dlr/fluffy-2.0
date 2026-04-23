import os
from nicegui import ui, app

# ---------- Auth state ----------
def is_logged_in() -> bool:
    return app.storage.user.get("logged_in", False)

# ---------- Shared navbar ----------
def navbar():
    with ui.header().classes("items-center justify-between px-6 py-3").style(
        "background: #005487; box-shadow: 0 2px 8px rgba(0,0,0,0.3);"
    ):
        with ui.row().classes("items-center gap-3"):
            ui.label("🥑").style("font-size: 1.6rem;")
            ui.label("Fluffy").style(
                "font-size: 1.4rem; font-weight: 700; color: white; letter-spacing: 0.04em;"
            )

        if is_logged_in():
            with ui.row().classes("items-center gap-1"):
                for label, route in [
                    ("Home", "/"),
                    ("Ceres6 Search", "/ceres6"),
                    ("Order Trends", "/order-trends"),
                    ("KPI Showcase", "/kpi"),
                ]:
                    ui.button(label, on_click=lambda r=route: ui.navigate.to(r)).props(
                        "flat"
                    ).style("color: white; font-weight: 500;")

                ui.separator().props("vertical").style("background: rgba(255,255,255,0.3); height:24px;")
                ui.button("Log out", on_click=do_logout).props("flat").style(
                    "color: #de7c00; font-weight: 500;"
                )


# ---------- Auth actions ----------
def do_logout():
    app.storage.user["logged_in"] = False
    ui.navigate.to("/")


# ---------- Pages ----------
@ui.page("/")
def home_page():
    navbar()
    if not is_logged_in():
        _render_login()
    else:
        from pages.home import render
        render()


@ui.page("/ceres6")
def ceres6_page():
    navbar()
    if not is_logged_in():
        ui.navigate.to("/")
        return
    from pages.ceres6_search import render
    render()


@ui.page("/order-trends")
def order_trends_page():
    navbar()
    if not is_logged_in():
        ui.navigate.to("/")
        return
    from pages.order_trends import render
    render()


@ui.page("/kpi")
def kpi_page():
    navbar()
    if not is_logged_in():
        ui.navigate.to("/")
        return
    from pages.kpi import render
    render()


# ---------- Login UI ----------
def _render_login():
    with ui.column().classes("items-center justify-center").style(
        "min-height: 70vh; width: 100%;"
    ):
        with ui.card().style(
            "width: 360px; padding: 2rem; border-radius: 16px; "
            "box-shadow: 0 4px 24px rgba(0,0,0,0.12);"
        ):
            with ui.column().classes("items-center gap-4 w-full"):
                ui.label("🥑").style("font-size: 3rem;")
                ui.label("Welcome to Fluffy").style(
                    "font-size: 1.4rem; font-weight: 700; color: #1a3a5c;"
                )
                ui.label("Feeding San Diego's internal toolkit").style(
                    "font-size: 0.85rem; color: #666; text-align: center;"
                )

                ui.separator()

                ui.button("Log in", on_click=_do_login).props("unelevated").style(
                    "width: 100%; background: #1a3a5c; color: white; "
                    "font-size: 1rem; font-weight: 600; border-radius: 8px; padding: 10px;"
                )


def _do_login():
    app.storage.user["logged_in"] = True
    ui.navigate.to("/")


# ---------- Run ----------
ui.run(
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8080)),
    reload=False,
    title="Fluffy",
    storage_secret=os.environ.get("STORAGE_SECRET", "fluffy-fsd-secret-change-me"),
    favicon="🥑",
)
