import flet as ft
from .base_log import BaseLogView
from models import DADLog

class DADLogView(BaseLogView):
    def __init__(self, page):
        columns_config = [
            ("project_id", ft.DataColumn(ft.Text("Project")), lambda i: ft.DataCell(ft.Text(i.project.name if i.project else "Global"))),
            ("id", ft.DataColumn(ft.Text("ID")), lambda i: ft.DataCell(ft.Text(str(i.id)))),
            ("type", ft.DataColumn(ft.Text("Type")), lambda i: ft.DataCell(ft.Text(i.type))),
            ("description", ft.DataColumn(ft.Text("Description")), lambda i: ft.DataCell(ft.Text(i.description))),
            ("status", ft.DataColumn(ft.Text("Status")), lambda i: ft.DataCell(ft.Text(i.status))),
            ("date_raised", ft.DataColumn(ft.Text("Date Raised")), lambda i: ft.DataCell(ft.Text(i.date_raised.strftime("%Y-%m-%d") if i.date_raised else ""))),
        ]
        
        super().__init__(
            page=page, 
            model_class=DADLog, 
            title="DAD Log", 
            columns_config=columns_config,
            icon=ft.Icons.LIST_ALT
        )

