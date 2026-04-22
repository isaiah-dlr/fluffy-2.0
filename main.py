import os
from nicegui import ui

def nav():
    with ui.row():
        ui.button('Home', on_click=lambda: ui.navigate.to('/'))
        ui.button('Ceres6', on_click=lambda: ui.navigate.to('/ceres6'))
        ui.button('KPI', on_click=lambda: ui.navigate.to('/kpi'))
        ui.button('Trends', on_click=lambda: ui.navigate.to('/trends'))

@ui.page('/')
def home():
    nav()
    ui.label('Home').classes('text-h4')

@ui.page('/ceres6')
def ceres6():
    nav()
    ui.label('Ceres6').classes('text-h4')

@ui.page('/kpi')
def kpi():
    nav()
    ui.label('KPI').classes('text-h4')

@ui.page('/trends')
def trends():
    nav()
    ui.label('Trends').classes('text-h4')

ui.run(host='0.0.0.0', port=int(os.getenv('PORT', '8080')))