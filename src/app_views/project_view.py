import flet as ft
from .base_log import BaseLogView
from models import Project
from database import get_db_context

class ProjectView(BaseLogView):
    def __init__(self, page=None):
        # Handle case where page might be None during init (though BaseLogView expects it)
        # ProjectView is instantiated in main.py, page is passed.
        
        columns_config = [
            ("id", ft.DataColumn(ft.Text("ID")), lambda i: ft.DataCell(ft.Text(str(i.id)))),
            ("name", ft.DataColumn(ft.Text("Name")), lambda i: ft.DataCell(
                ft.TextButton(
                    content=ft.Text(i.name, weight="bold", color=ft.Colors.BLUE),
                    on_click=lambda e: self.select_project(i),
                    style=ft.ButtonStyle(padding=0)
                )
            )),
            ("status", ft.DataColumn(ft.Text("Status")), lambda i: self.get_status_cell(i)),
        ]
        
        super().__init__(
            page=page, 
            model_class=Project, 
            title="Projects", 
            columns_config=columns_config,
            icon=ft.Icons.ACCOUNT_TREE,
            enable_project_filter=False
        )
    
    def get_status_cell(self, item):
        color = ft.Colors.GREY
        if item.status == 'Active': color = ft.Colors.GREEN
        elif item.status == 'Closed': color = ft.Colors.BLUE
        elif item.status == 'On-Hold': color = ft.Colors.AMBER
        
        return ft.DataCell(
            ft.Container(
                content=ft.Text(item.status, color=ft.Colors.WHITE, size=10),
                bgcolor=color,
                padding=5,
                border_radius=5
            )
        )

    def select_project(self, project):
        self.page.session.set("project_id", project.id)
        print(f"ProjectView: Selected {project.id}, navigating to /plan")
        self.page.open(ft.SnackBar(ft.Text(f"Selected project: {project.name}")))
        self.page.go("/plan")

    def delete_item(self, item):
        # Override delete to add specific checks if needed, or use default.
        # Default BaseLogView delete is generic. 
        # Project deletion might need extra checks (cascade is handled by DB usually).
        super().delete_item(item)

