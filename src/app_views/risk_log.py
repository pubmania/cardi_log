import flet as ft
from database import get_db_context
from models import RiskLog, Project
from .base_log import BaseLogView

class RiskLogView(BaseLogView):
    def __init__(self, page: ft.Page):
        # Define Columns Configuration
        # Tuple: (Key/Field Name, DataColumn, Cell Function)
        columns_config = [
            ("Project", ft.DataColumn(ft.Text("Project")), lambda r: ft.DataCell(ft.Text(r.project.name if r.project else "Unknown"))),
            ("ID", ft.DataColumn(ft.Text("ID")), lambda r: ft.DataCell(ft.Text(str(r.id)))),
            ("Title", ft.DataColumn(ft.Text("Title")), lambda r: ft.DataCell(ft.Text(r.title))),
            ("Description", ft.DataColumn(ft.Text("Description")), lambda r: ft.DataCell(ft.Text(r.description))),
            ("Status", ft.DataColumn(ft.Text("Status")), lambda r: ft.DataCell(ft.Text(r.status))),
            ("Type", ft.DataColumn(ft.Text("Type")), lambda r: ft.DataCell(ft.Text(r.type))),
            ("Workstream", ft.DataColumn(ft.Text("Workstream")), lambda r: ft.DataCell(ft.Text(r.workstream))),
            ("Probability", ft.DataColumn(ft.Text("Probability")), lambda r: ft.DataCell(ft.Text(r.probability))),
            ("Impact", ft.DataColumn(ft.Text("Impact")), lambda r: ft.DataCell(ft.Text(r.impact))),
            ("RAG", ft.DataColumn(ft.Text("RAG")), lambda r: self.get_rag_cell(r)),
            ("Date Raised", ft.DataColumn(ft.Text("Date Raised")), lambda r: ft.DataCell(ft.Text(str(r.date_raised) if r.date_raised else ""))),
            ("Raised By", ft.DataColumn(ft.Text("Raised By")), lambda r: ft.DataCell(ft.Text(r.raised_by))),
            ("Response Strategy", ft.DataColumn(ft.Text("Response Strategy")), lambda r: ft.DataCell(ft.Text(r.response_strategy))),
            ("Response Action", ft.DataColumn(ft.Text("Response Action")), lambda r: ft.DataCell(ft.Text(r.response_action))),
            ("Owner", ft.DataColumn(ft.Text("Owner")), lambda r: ft.DataCell(ft.Text(r.action_owner))),
            ("Notes", ft.DataColumn(ft.Text("Notes")), lambda r: ft.DataCell(ft.Text(r.notes))),
        ]
        
        super().__init__(page, RiskLog, "Risk Log", columns_config, icon=ft.Icons.WARNING_AMBER)
        self.custom_page = page 

    def save_to_db(self, item, data):
        # Custom Logic: Calculate RAG
        prob = data.get('probability')
        imp = data.get('impact')
        
        if prob == "High" and imp == "High":
            data['rag'] = "Red"
        elif prob == "Low" and imp == "Low":
            data['rag'] = "Green"
        else:
            data['rag'] = "Amber"
            
        # Call Parent to handle actual DB write
        super().save_to_db(item, data)



