import flet as ft
from .base_log import BaseLogView
from models import IssuesLog

class IssueLogView(BaseLogView):
    def __init__(self, page):
        columns_config = [
            ("project_id", ft.DataColumn(ft.Text("Project")), lambda i: ft.DataCell(ft.Text(i.project.name if i.project else "Global"))),
            ("id", ft.DataColumn(ft.Text("ID")), lambda i: ft.DataCell(ft.Text(str(i.id)))),
            ("title", ft.DataColumn(ft.Text("Title")), lambda i: ft.DataCell(ft.Text(i.title, weight="bold"))),
            ("status", ft.DataColumn(ft.Text("Status")), lambda i: ft.DataCell(ft.Text(i.status))),
            ("rag", ft.DataColumn(ft.Text("RAG")), lambda i: self.get_rag_cell(i)),
            ("action_owner", ft.DataColumn(ft.Text("Owner")), lambda i: ft.DataCell(ft.Text(i.action_owner or ""))),
            ("target_closure_date", ft.DataColumn(ft.Text("Target Date")), lambda i: ft.DataCell(ft.Text(i.target_closure_date.strftime("%Y-%m-%d") if i.target_closure_date else ""))),
        ]
        
        super().__init__(
            page=page, 
            model_class=IssuesLog, 
            title="Issue Log", 
            columns_config=columns_config,
            icon=ft.Icons.ERROR
        )

