import os
from nicegui import ui

def navbar():
    with ui.header().classes('items-center justify-between bg-blue-600 text-white px-6'):
        ui.label('FluffyApp').classes('text-xl font-bold')
        with ui.row():
            ui.button('Home',          on_click=lambda: ui.navigate.to('/')).props('flat color=white')
            ui.button('Ceres6 Search', on_click=lambda: ui.navigate.to('/ceres6')).props('flat color=white')
            ui.button('KPI',           on_click=lambda: ui.navigate.to('/kpi')).props('flat color=white')
            ui.button('Order Trends',  on_click=lambda: ui.navigate.to('/order-trends')).props('flat color=white')

@ui.page('/')
def home():
    navbar()
    from pages.home import render
    render()

@ui.page('/ceres6')
def ceres6():
    navbar()
    from pages.ceres6_search import render
    render()

@ui.page('/kpi')
def kpi():
    navbar()
    from pages.kpi import render
    render()

@ui.page('/order-trends')
def order_trends():
    navbar()
    from pages.order_trends import render
    render()

ui.run(
    host='0.0.0.0',
    port=int(os.environ.get('PORT', 8080)),
    reload=False,
    title='FluffyApp'
)