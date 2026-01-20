import flet as ft
from .base_log import BaseLogView
from models import ActionsLog

class ActionLogView(BaseLogView):
    def __init__(self, page):
        columns_config = [
            ("project_id", ft.DataColumn(ft.Text("Project")), lambda i: ft.DataCell(ft.Text(i.project.name if i.project else "Global"))),
            ("id", ft.DataColumn(ft.Text("ID")), lambda i: ft.DataCell(ft.Text(str(i.id)))),
            ("description", ft.DataColumn(ft.Text("Description")), lambda i: ft.DataCell(ft.Text(i.description))),
            ("status", ft.DataColumn(ft.Text("Status")), lambda i: ft.DataCell(ft.Text(i.status))),
            ("owner", ft.DataColumn(ft.Text("Owner")), lambda i: ft.DataCell(ft.Text(i.owner or ""))),
            ("target_end_date", ft.DataColumn(ft.Text("Target Date")), lambda i: ft.DataCell(ft.Text(i.target_end_date.strftime("%Y-%m-%d") if i.target_end_date else ""))),
        ]
        
        super().__init__(
            page=page, 
            model_class=ActionsLog, 
            title="Action Log", 
            columns_config=columns_config,
            icon=ft.Icons.CHECK_CIRCLE
        )

