import flet as ft
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import RiskLog, IssuesLog, ActionsLog, ChangeLog, Project, ProjectTask
from utils_data import generate_native_portfolio_gantt_chart, generate_native_gantt_chart, generate_gantt_html

from .base_page import BasePageView

class DashboardView(BasePageView):
    def __init__(self, page):
        super().__init__(page, "Dashboard", ft.Icons.DASHBOARD)
        # self.expand = True # Handled by BasePageView
        # Project Dropdown handled by BasePageView
        
        self.risk_count = 0
        self.issue_count = 0
        self.action_count = 0
        self.change_count = 0
        self.top_risks = []
        self.top_issues = []
        self.top_actions = []
        self.risk_profile = {"Red": 0, "Amber": 0, "Green": 0}
        self.issue_status = {"Open": 0, "Closed": 0}
        self.view_mode = "Days"
        
        self.padding = 20
        # self.content initialized by BasePageView
        # self.content = ft.Column([], scroll=ft.ScrollMode.AUTO)

        self.load_data()

    def did_mount(self):
        if self.page:
            # Theme handling managed by BasePageView render_header, but we can double check
            pass
            
            # Check resize on mount to ensure correct layout
            self.handle_resize(None)

    def handle_resize(self, e):
        # Override BasePageView handle_resize to simply reload/render
        if not self.page: return
        project_id = self.page.session.get("project_id")
        self.render_dashboard(project_id)
        self.page.update()

    def on_view_mode_change(self, e):
        self.view_mode = e.control.value
        self.load_data()

    # load_projects and on_project_change handled by BasePageView

    def load_data(self):
        # BasePageView calls load_projects internally if needed, or we can assume it's done.
        # But load_data is called by BasePageView on_project_change.
        pass # load_projects is done by BasePageView init
        
        from database import get_db_context
        with get_db_context() as db:
            project_id = self.page.session.get("project_id") if self.page else None
            
            # Base queries
            risk_query = db.query(RiskLog)
            issue_query = db.query(IssuesLog)
            action_query = db.query(ActionsLog)
            change_query = db.query(ChangeLog)
            
            if project_id:
                risk_query = risk_query.filter(RiskLog.project_id == project_id)
                issue_query = issue_query.filter(IssuesLog.project_id == project_id)
                action_query = action_query.filter(ActionsLog.project_id == project_id)
                change_query = change_query.filter(ChangeLog.project_id == project_id)
            
            # Counts
            self.risk_count = risk_query.count()
            self.issue_count = issue_query.count()
            self.action_count = action_query.count()
            self.change_count = change_query.count()
            
            # Top Items
            self.top_risks = risk_query.order_by(RiskLog.rag == 'Red', RiskLog.rag == 'Amber', RiskLog.id.desc()).limit(5).all()
            self.top_issues = issue_query.filter(IssuesLog.status == 'Open').order_by(IssuesLog.id.desc()).limit(5).all()
            self.top_actions = action_query.filter(ActionsLog.status == 'Open').order_by(ActionsLog.target_end_date).limit(5).all()
            
            # Risk Profile
            rag_counts = risk_query.with_entities(RiskLog.rag, func.count(RiskLog.rag)).group_by(RiskLog.rag).all()
            self.risk_profile = {"Red": 0, "Amber": 0, "Green": 0}
            for rag, count in rag_counts:
                if rag in self.risk_profile:
                    self.risk_profile[rag] = count
            
            # Issue Status
            status_counts = issue_query.with_entities(IssuesLog.status, func.count(IssuesLog.status)).group_by(IssuesLog.status).all()
            self.issue_status = {"Open": 0, "Closed": 0}
            for status, count in status_counts:
                if status in self.issue_status:
                    self.issue_status[status] = count
            
            # Rebuild content if needed
            target_page = self.page
            if not target_page: 
                 # Fallback if page not yet mounted but we need to verify structure?
                 # Assuming default desktop if no page
                 is_mobile = False
            else:
                 is_mobile = target_page.width < 800

            self.render_dashboard(project_id)
                
            if self.page:
                self.page.update()

    def render_dashboard(self, project_id):
        # Unified Responsive Layout
        
        # Helper for card columns with stretch alignment
        def card_col(card, col_def):
             # Ensure card container has no fixed width so it stretches
             if isinstance(card, ft.Card) and card.content:
                 card.content.width = None
             return ft.Column([card], col=col_def, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        self.content.controls = [
            # Header
            self.render_header(),
            
            ft.Divider(),
            
            ft.Column(
                [
                    # Summary Cards using ResponsiveRow
                    ft.ResponsiveRow(
                        [
                            card_col(self.create_summary_card("Risks", self.risk_count, ft.Icons.WARNING_AMBER, ft.Colors.ORANGE, "/risks"), {"xs": 12, "sm": 6, "md": 3}),
                            card_col(self.create_summary_card("Issues", self.issue_count, ft.Icons.ERROR_OUTLINE, ft.Colors.RED, "/issues"), {"xs": 12, "sm": 6, "md": 3}),
                            card_col(self.create_summary_card("Actions", self.action_count, ft.Icons.TASK_ALT, ft.Colors.BLUE, "/actions"), {"xs": 12, "sm": 6, "md": 3}),
                            card_col(self.create_summary_card("Changes", self.change_count, ft.Icons.CHANGE_CIRCLE_OUTLINED, ft.Colors.PURPLE, "/changes"), {"xs": 12, "sm": 6, "md": 3}),
                        ],
                        spacing=10,
                        run_spacing=10
                    ),
                    ft.Divider(),
                    # Charts Row
                    ft.ResponsiveRow(
                        [
                            ft.Column([self.create_risk_chart()], col={"md": 6, "xs": 12}, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                            ft.Column([self.create_issue_chart()], col={"md": 6, "xs": 12}, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(),
                    # Top Items Row
                    ft.ResponsiveRow(
                        [
                            ft.Column([
                                ft.Text("Top 5 High Risks", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
                                ft.Container(
                                    content=ft.Row([ft.Column([self.create_top_risks_table()], scroll=ft.ScrollMode.ALWAYS)], scroll=ft.ScrollMode.ALWAYS)
                                ),
                            ], col={"md": 4, "xs": 12}),
                            ft.Column([
                                ft.Text("Top 5 Open Issues", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE),
                                ft.Container(
                                    content=ft.Row([ft.Column([self.create_top_issues_table()], scroll=ft.ScrollMode.ALWAYS)], scroll=ft.ScrollMode.ALWAYS)
                                ),
                            ], col={"md": 4, "xs": 12}),
                            ft.Column([
                                ft.Text("Top 5 Open Actions", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE),
                                ft.Container(
                                    content=ft.Row([ft.Column([self.create_top_actions_table()], scroll=ft.ScrollMode.ALWAYS)], scroll=ft.ScrollMode.ALWAYS)
                                ),
                            ], col={"md": 4, "xs": 12}),
                        ],
                    ),
                    ft.Divider(),
                    # Portfolio Gantt
                    ft.Column([
                        ft.Container(
                            content=self.create_portfolio_gantt() if not project_id else self.create_project_summary_gantt(project_id)
                        )
                    ], 
                    visible=True,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True
            )
        ]
        if self.uid:
            self.content.update()

    def create_summary_card(self, title, count, icon, color, route):
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(icon, color=color, size=40),
                        ft.Text(str(count), size=40, weight=ft.FontWeight.BOLD),
                        ft.Text(title, size=16),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=20,
                # width=200, # Removed for responsiveness
                height=150,
                on_click=lambda e: self.page.go(route),
                ink=True,
            )
        )

    def create_risk_chart(self):
        return ft.Container(
            content=ft.Column([
                ft.Text("Risk Profile", size=16, weight=ft.FontWeight.BOLD),
                ft.BarChart(
                    bar_groups=[
                        ft.BarChartGroup(
                            x=0,
                            bar_rods=[
                                ft.BarChartRod(
                                    from_y=0,
                                    to_y=self.risk_profile["Red"],
                                    width=40,
                                    color=ft.Colors.RED,
                                    tooltip=str(self.risk_profile["Red"]),
                                    border_radius=0,
                                ),
                            ],
                        ),
                        ft.BarChartGroup(
                            x=1,
                            bar_rods=[
                                ft.BarChartRod(
                                    from_y=0,
                                    to_y=self.risk_profile["Amber"],
                                    width=40,
                                    color=ft.Colors.AMBER,
                                    tooltip=str(self.risk_profile["Amber"]),
                                    border_radius=0,
                                ),
                            ],
                        ),
                        ft.BarChartGroup(
                            x=2,
                            bar_rods=[
                                ft.BarChartRod(
                                    from_y=0,
                                    to_y=self.risk_profile["Green"],
                                    width=40,
                                    color=ft.Colors.GREEN,
                                    tooltip=str(self.risk_profile["Green"]),
                                    border_radius=0,
                                ),
                            ],
                        ),
                    ],
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    left_axis=ft.ChartAxis(
                        labels_size=40, title=ft.Text("Count"), title_size=40
                    ),
                    bottom_axis=ft.ChartAxis(
                        labels=[
                            ft.ChartAxisLabel(
                                value=0, label=ft.Container(ft.Text("Red"), padding=10)
                            ),
                            ft.ChartAxisLabel(
                                value=1, label=ft.Container(ft.Text("Amber"), padding=10)
                            ),
                            ft.ChartAxisLabel(
                                value=2, label=ft.Container(ft.Text("Green"), padding=10)
                            ),
                        ],
                        labels_size=40,
                    ),
                    horizontal_grid_lines=ft.ChartGridLines(
                        color=ft.Colors.GREY_300, width=1, dash_pattern=[3, 3]
                    ),
                    tooltip_bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.GREY_300),
                    max_y=max(self.risk_profile.values()) + 1 if self.risk_profile else 5,
                    interactive=True,
                    expand=True,
                ),
            ]),
            width=400,
            height=300,
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY_200),
            border_radius=10,
        )

    def create_issue_chart(self):
        return ft.Container(
            content=ft.Column([
                ft.Text("Issue Status", size=16, weight=ft.FontWeight.BOLD),
                ft.PieChart(
                    sections=[
                        ft.PieChartSection(
                            self.issue_status["Open"],
                            title=f"{self.issue_status['Open']}",
                            color=ft.Colors.AMBER,
                            radius=50,
                        ),
                        ft.PieChartSection(
                            self.issue_status["Closed"],
                            title=f"{self.issue_status['Closed']}",
                            color=ft.Colors.GREY,
                            radius=50,
                        ),
                    ],
                    sections_space=0,
                    center_space_radius=40,
                    expand=True,
                ),
                ft.Row([
                    ft.Row([ft.Container(width=10, height=10, bgcolor=ft.Colors.AMBER), ft.Text("Open")]),
                    ft.Row([ft.Container(width=10, height=10, bgcolor=ft.Colors.GREY), ft.Text("Closed")]),
                ], alignment=ft.MainAxisAlignment.CENTER),
            ]),
            width=400,
            height=300,
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY_200),
            border_radius=10,
        )

    def create_top_risks_table(self):
        rows = []
        for risk in self.top_risks:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(risk.id))),
                        ft.DataCell(ft.Text(risk.title, tooltip=risk.title, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                        ft.DataCell(ft.Container(
                            width=15, height=15, border_radius=15,
                            bgcolor=ft.Colors.RED if risk.rag == 'Red' else ft.Colors.AMBER if risk.rag == 'Amber' else ft.Colors.GREEN,
                            tooltip=risk.rag
                        )),
                    ]
                )
            )
        
        if not rows:
            return ft.Text("No high risks found.")

        return ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Title")),
                ft.DataColumn(ft.Text("RAG")),
            ],
            rows=rows,
            column_spacing=10,
            heading_row_height=30,
            data_row_min_height=30,
        )

    def create_top_issues_table(self):
        rows = []
        for issue in self.top_issues:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(issue.id))),
                        ft.DataCell(ft.Text(issue.title, tooltip=issue.title, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                        ft.DataCell(ft.Container(
                            width=15, height=15, border_radius=15,
                            bgcolor=ft.Colors.RED if issue.rag == 'Red' else ft.Colors.AMBER if issue.rag == 'Amber' else ft.Colors.GREEN,
                            tooltip=issue.rag
                        )),
                    ]
                )
            )
        
        if not rows:
            return ft.Text("No open issues found.")

        return ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Title")),
                ft.DataColumn(ft.Text("RAG")),
            ],
            rows=rows,
            column_spacing=10,
            heading_row_height=30,
            data_row_min_height=30,
        )

    def create_top_actions_table(self):
        rows = []
        for action in self.top_actions:
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(action.id))),
                        ft.DataCell(ft.Text(action.description, tooltip=action.description, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)),
                        ft.DataCell(ft.Text(str(action.target_end_date))),
                    ]
                )
            )
        
        if not rows:
            return ft.Text("No open actions found.")

        return ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Title")),
                ft.DataColumn(ft.Text("Due Date")),
            ],
            rows=rows,
            column_spacing=10,
            heading_row_height=30,
            data_row_min_height=30,
        )



    def export_dashboard_gantt(self, e):
        from database import get_db_context
        with get_db_context() as db:
            try:
                print("Export Dashboard Gantt Clicked")
                project_id = self.page.session.get("project_id")
                
                filepath = None
                if not project_id:
                    # Portfolio Export
                    print("Exporting Portfolio...")
                    projects = db.query(Project).all()
                    projects_data = []
                    for p in projects:
                        p_tasks = db.query(ProjectTask).filter(ProjectTask.project_id == p.id).all()
                        p_start = min([t.start_date for t in p_tasks if t.start_date], default=None)
                        p_end = max([t.end_date for t in p_tasks if t.end_date], default=None)
                        if p_start and p_end:
                             projects_data.append({
                                'name': p.name,
                                'start_date': p_start,
                                'end_date': p_end,
                                'status': p.status 
                            })
                    if projects_data:
                        filepath = generate_gantt_html(is_portfolio=True, projects_data=projects_data)
                else:
                    # Single Project Export (Top Level Only)
                    print(f"Exporting Project {project_id}...")
                    tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
                    top_level_tasks = [t for t in tasks if "." not in t.task_id]
                    from utils_data import get_task_sort_key
                    top_level_tasks.sort(key=lambda t: get_task_sort_key(t.task_id))
                    
                    if top_level_tasks:
                         filepath = generate_gantt_html(tasks=top_level_tasks, title="Project Top Level Timeline")
                
                print(f"Generated filepath: {filepath}")
                if filepath and self.page:
                    import pathlib
                    file_uri = pathlib.Path(filepath).as_uri()
                    print(f"Launching URI: {file_uri}")
                    self.page.launch_url(file_uri)
                    
            except Exception as ex:
                print(f"Export failed: {ex}")
                import traceback
                traceback.print_exc()

    def create_portfolio_gantt(self):
        from database import get_db_context
        with get_db_context() as db:
            projects = db.query(Project).all()
            projects_data = []
            for p in projects:
                p_tasks = db.query(ProjectTask).filter(ProjectTask.project_id == p.id).all()
                p_start = min([t.start_date for t in p_tasks if t.start_date], default=None)
                p_end = max([t.end_date for t in p_tasks if t.end_date], default=None)
                
                if p_start and p_end:
                    projects_data.append({
                        'name': p.name,
                        'start_date': p_start,
                        'end_date': p_end,
                        'status': p.status 
                    })
            
            if not projects_data:
                return ft.Container(ft.Text("No project data for Gantt"), padding=20)
            
            chart = generate_native_portfolio_gantt_chart(projects_data, expand_chart=False, view_mode=self.view_mode)
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Portfolio Roadmap", size=20, weight=ft.FontWeight.BOLD),
                        ft.Row([
                            ft.Dropdown(
                                value=self.view_mode,
                                options=[
                                    ft.dropdown.Option("Days"),
                                    ft.dropdown.Option("Weeks"),
                                    ft.dropdown.Option("Months"),
                                    ft.dropdown.Option("Quarters"),
                                    ft.dropdown.Option("Years"),
                                ],
                                on_change=self.on_view_mode_change,
                                width=120,
                                label="Scale",
                                content_padding=5
                            ),
                            ft.IconButton(ft.Icons.OPEN_IN_BROWSER, tooltip="Open detailed interactive chart in browser", on_click=self.export_dashboard_gantt)
                        ], wrap=True)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                    ft.Row([
                      ft.Container(chart, width=1500)
                    ], scroll=ft.ScrollMode.ALWAYS)
                ], horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                padding=20,
                border=ft.border.all(1, ft.Colors.GREY_200),
                border_radius=10,
            )

    def create_project_summary_gantt(self, project_id):
        from database import get_db_context
        with get_db_context() as db:
            # Fetch all tasks for project
            tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
            
            # Filter for Top Level Tasks (no dot in ID)
            top_level_tasks = [t for t in tasks if "." not in t.task_id]
            
            # Sort them properly
            from utils_data import get_task_sort_key
            top_level_tasks.sort(key=lambda t: get_task_sort_key(t.task_id))
            
            if not top_level_tasks:
                 return ft.Container(ft.Text("No top-level tasks found for this project."), padding=20)

            chart = generate_native_gantt_chart(top_level_tasks, expand_chart=False, view_mode=self.view_mode)
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Project Timeline (Top Level)", size=20, weight=ft.FontWeight.BOLD),
                        ft.Row([
                            ft.Dropdown(
                                value=self.view_mode,
                                options=[
                                    ft.dropdown.Option("Days"),
                                    ft.dropdown.Option("Weeks"),
                                    ft.dropdown.Option("Months"),
                                    ft.dropdown.Option("Quarters"),
                                    ft.dropdown.Option("Years"),
                                ],
                                on_change=self.on_view_mode_change,
                                width=120,
                                label="Scale",
                                content_padding=5
                            ),
                            ft.IconButton(ft.Icons.OPEN_IN_BROWSER, tooltip="Open detailed interactive chart in browser", on_click=self.export_dashboard_gantt)
                        ], wrap=True)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                    ft.Row([
                      ft.Container(chart, width=1500)
                    ], scroll=ft.ScrollMode.ALWAYS)
                ], horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                padding=20,
                border=ft.border.all(1, ft.Colors.GREY_200),
                border_radius=10,
            )

