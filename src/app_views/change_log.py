import flet as ft
from .base_log import BaseLogView
from models import ChangeLog

class ChangeLogView(BaseLogView):
    def __init__(self, page):
        columns_config = [
            ("project_id", ft.DataColumn(ft.Text("Project")), lambda i: ft.DataCell(ft.Text(i.project.name if i.project else "Global"))),
            ("id", ft.DataColumn(ft.Text("ID")), lambda i: ft.DataCell(ft.Text(str(i.id)))),
            ("type", ft.DataColumn(ft.Text("Type")), lambda i: ft.DataCell(ft.Text(i.type))),
            ("title", ft.DataColumn(ft.Text("Title")), lambda i: ft.DataCell(ft.Text(i.title, weight="bold"))),
            ("status", ft.DataColumn(ft.Text("Status")), lambda i: ft.DataCell(ft.Text(i.status))),
            ("submitted_by", ft.DataColumn(ft.Text("Submitted By")), lambda i: ft.DataCell(ft.Text(i.submitted_by or ""))),
            ("date_received", ft.DataColumn(ft.Text("Date Received")), lambda i: ft.DataCell(ft.Text(i.date_received.strftime("%Y-%m-%d") if i.date_received else ""))),
            ("impacts", ft.DataColumn(ft.Text("Impacts")), lambda i: ft.DataCell(ft.Text(
                ", ".join([label for label, val in [("Scope", i.scope_impact), ("Schedule", i.schedule_impact), ("Cost", i.cost_impact)] if val])
            ))),
        ]
        
        super().__init__(
            page=page, 
            model_class=ChangeLog, 
            title="Change Log", 
            columns_config=columns_config,
            icon=ft.Icons.CHANGE_CIRCLE
        )

