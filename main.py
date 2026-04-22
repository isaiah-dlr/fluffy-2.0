import os
from nicegui import ui

@ui.page('/')
def home():
    ui.label('FluffyApp').classes('text-h4')
    ui.label('NiceGUI + Render test is working')
    with ui.row():
        ui.button('Ceres6')
        ui.button('KPI')
        ui.button('Trends')

ui.run(host='0.0.0.0', port=int(os.getenv('PORT', '8080')))