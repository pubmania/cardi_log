import flet as ft
from flet.plotly_chart import PlotlyChart
from sqlalchemy.orm import Session
from database import get_db
from models import Project, ProjectTask
from utils_data import generate_template_dataframe, export_tasks_to_file, import_tasks_from_file, generate_gantt_html, generate_gantt_chart, generate_portfolio_gantt_chart, generate_task_id, generate_native_gantt_chart, generate_native_portfolio_gantt_chart, get_task_sort_key, generate_subtask_id, update_parent_completion, update_hierarchy_dates
from utils import set_required, get_visible_columns, show_column_selector_dialog, get_settings, create_help_button
import base64
from datetime import datetime
import os
import webbrowser

from .base_page import BasePageView

class ProjectPlanView(BasePageView):
    def __init__(self, page: ft.Page = None):
        super().__init__(page, "Project Plan", ft.Icons.EVENT_NOTE)
        self.custom_page = page # Still keeping this just in case, though BasePageView stores self.page
        self.view_mode = "Days"
        self._last_is_mobile = None 
        self.selected_tab_index = 0
        
        # Project Dropdown handled by BasePageView
        
        # File Pickers
        self.import_picker = ft.FilePicker(on_result=self.on_import_result)
        self.template_picker = ft.FilePicker(on_result=self.on_template_save_result)
        self.export_picker = ft.FilePicker(on_result=self.on_export_save_result)
        
        # self.content initialized by BasePageView
        
        self.task_table = ft.DataTable(columns=[], rows=[], column_spacing=10)
        
        self.load_data()

    def did_mount(self):
        if self.page:
            try:
                # Add file pickers
                for picker in [self.import_picker, self.template_picker, self.export_picker]:
                     if picker not in self.page.overlay:
                         self.page.overlay.append(picker)

                # Theme handling managed by BasePageView render_header

                self.handle_resize(None)
                
            except Exception as e:
                print(f"Error in did_mount: {e}")
                import traceback
                traceback.print_exc()

    def handle_resize(self, e):
        # Override BasePageView
        if not self.page: return
        self.load_data()

    def open_column_selector(self, e):
        from utils import show_column_selector_dialog
        
        # Define available columns
        columns = ["Task ID", "Task Name", "Resource", "Start", "End", "%", "Actions"]
        
        def on_columns_changed(visible_columns):
            # Save settings
            # We need to save per view? Or just generic Project Plan settings
            pass # The util helper handles saving if we pass a key
            # But the util helper `show_column_selector_dialog` logic needs to be checked.
            # Assuming it takes (page, key, all_cols, on_change)
            
            # For now, just reload data to apply changes
            self.load_data()
            
        show_column_selector_dialog(self.page, "Project Plan", columns, on_columns_changed)

    def open_filter_dialog(self, e):
        # Placeholder for filter dialog
        if self.page:
            self.page.open(ft.SnackBar(ft.Text("Filter functionality coming soon!")))
            self.page.update()

    def on_tab_change(self, e):
        self.selected_tab_index = e.control.selected_index
        self.load_data()

    def render_mobile_view(self, tasks):
        self.content.controls.clear()
        
        # 1. Header (Stacked for Mobile)
        # 1. Header using BasePageView for Mobile too?
        # BasePageView render_header might be too wide?
        # Let's try to reuse it but passing actions might overflow
        # If we use render_header with fewer actions or same actions
        extra_actions = [
             ft.Row(
                [
                    ft.IconButton(ft.Icons.VIEW_COLUMN, on_click=self.open_column_selector, tooltip="Columns", icon_color=ft.Colors.PRIMARY),
                    ft.IconButton(ft.Icons.FILTER_LIST, on_click=self.open_filter_dialog, tooltip="Filter", icon_color=ft.Colors.PRIMARY),
                    ft.IconButton(ft.Icons.FILE_UPLOAD, on_click=self.import_picker.pick_files, tooltip="Import", icon_color=ft.Colors.PRIMARY),
                    ft.IconButton(ft.Icons.FILE_DOWNLOAD, on_click=self.export_tasks, tooltip="Export", icon_color=ft.Colors.PRIMARY),
                    ft.IconButton(ft.Icons.ADD, on_click=self.open_add_task_dialog, tooltip="Add Task", icon_color=ft.Colors.PRIMARY),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True
             )
        ]
        
        # 1. Header (Stacked for Mobile)
        # Use BasePageView responsive header
        extra_actions = [
            ft.IconButton(ft.Icons.VIEW_COLUMN, on_click=self.open_column_selector, tooltip="Columns", icon_color=ft.Colors.PRIMARY),
            ft.IconButton(ft.Icons.FILTER_LIST, on_click=self.open_filter_dialog, tooltip="Filter", icon_color=ft.Colors.PRIMARY),
            ft.IconButton(ft.Icons.FILE_UPLOAD, on_click=self.import_picker.pick_files, tooltip="Import", icon_color=ft.Colors.PRIMARY),
            ft.IconButton(ft.Icons.FILE_DOWNLOAD, on_click=self.export_tasks, tooltip="Export", icon_color=ft.Colors.PRIMARY),
            ft.IconButton(ft.Icons.ADD, on_click=self.open_add_task_dialog, tooltip="Add Task", icon_color=ft.Colors.PRIMARY),
        ]
        
        mobile_header = self.render_header(extra_actions=extra_actions)

        # 2. Content
        cards = [self.create_mobile_card(t) for t in tasks]
        
        # Prepare Gantt Content (Dashboard Logic)
        gantt_content = ft.Container(ft.Text("Select Gantt Tab"), padding=20)
        if self.selected_tab_index == 0:
            if hasattr(self, 'gantt_chart_content'):
                 gantt_content = self.gantt_chart_content

        mobile_tabs = ft.Tabs(
            selected_index=self.selected_tab_index,
            animation_duration=300,
            on_change=self.on_tab_change,
            tabs=[
                ft.Tab(
                    text="Gantt Chart",
                    icon=ft.Icons.BAR_CHART,
                    content=gantt_content,
                ),
                ft.Tab(
                    text="Task List",
                    icon=ft.Icons.LIST,
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.ListView(cards, expand=True, spacing=10, padding=10)
                            ],
                            expand=True
                        ),
                        expand=True
                    )
                )
            ],
            expand=True,
        )

        self.content.controls.extend([
            mobile_header,
            ft.Divider(),
            mobile_tabs
        ])

    def on_view_mode_change(self, e):
        self.view_mode = e.control.value
        self.load_data()

    def create_mobile_card(self, task):
        # Check if it's a VirtualTask (All Projects view) or real ProjectTask
        is_virtual = not hasattr(task, "id") 
        indent = 0
        if not is_virtual and task.task_id:
             indent = task.task_id.count('.')
        left_padding = indent * 20
        # Actions
        actions_row = ft.Row([], spacing=0)
        if not is_virtual:
            actions_row.controls = [
                ft.IconButton(ft.Icons.PLAYLIST_ADD, icon_color=ft.Colors.GREEN, icon_size=20, on_click=lambda e, t=task: self.show_task_dialog(parent_task=t), disabled=(task.task_id.count('.') >= 2 if task.task_id else True)),
                ft.IconButton(ft.Icons.EDIT, icon_color=ft.Colors.BLUE, icon_size=20, on_click=lambda e, t=task: self.open_edit_task_dialog(t)),
                ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, icon_size=20, on_click=lambda e, t=task: self.delete_task(t)),
            ]
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(task.task_name, weight=ft.FontWeight.BOLD, size=16, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(f"{task.completion}%", size=12, color=ft.Colors.GREEN if task.completion == 100 else ft.Colors.BLUE)
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        ft.Text(f"ID: {task.task_id} | Res: {task.resource}", size=12, color=ft.Colors.GREY_400),
                        ft.Row(
                            [
                                ft.Text(f"{task.start_date} -> {task.end_date}", size=12),
                                actions_row
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        )
                    ],
                    spacing=5
                ),
                padding=ft.padding.only(left=10 + left_padding, top=10, right=10, bottom=10)
            ) 
        )

    # load_projects and on_project_change handled by BasePageView

    def open_gantt_browser(self, e, is_portfolio=False):
        try:
            filepath = None
            filename = "gantt_chart.html"
            print("DEBUG: open_gantt_browser - filename: ", filename)
            # Ensure assets directory exists usually main.py handles it but good to be safe
            # Use path relative to this file to find src/assets
            # This file is in src/views/project_plan.py
            current_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(current_dir)
            assets_dir = os.path.join(src_dir, "assets")
            print("DEBUG: open_gantt_browser - assets_dir: ", assets_dir)
            
            if not os.path.exists(assets_dir):
                # Fallback to CWD/assets if src/assets not found (though unlikely for this project structure)
                cwd_assets = os.path.join(os.getcwd(), "assets")
                if os.path.exists(cwd_assets):
                    assets_dir = cwd_assets
                else:
                    os.makedirs(assets_dir)
            
            target_path = os.path.join(assets_dir, filename)

            if is_portfolio:
                # Fetch portfolio data
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
                    # We need to manually generate here to control path
                    fig = generate_portfolio_gantt_chart(projects_data, theme_mode="dark")
            else:
                project_id = self.page.session.get("project_id")
                if not project_id:
                    self.page.open(ft.SnackBar(ft.Text("Please select a project first")))
                    self.page.update()
                    return
                
                # Manual generation
                fig = generate_gantt_chart(project_id, theme_mode="dark")
                
            if fig:
                # Ensure dark background for standalone HTML
                fig.update_layout(paper_bgcolor='#1a1a1a', plot_bgcolor='#1a1a1a')
                fig.write_html(target_path)
                
                if self.page.web:
                    self.page.launch_url(f"/{filename}")
                    self.page.open(ft.SnackBar(ft.Text("Opened chart in new tab")))
                else:
                    self.page.launch_url(f"file:///{target_path}")
                    self.page.open(ft.SnackBar(ft.Text(f"Opened chart in browser: {target_path}")))
            else:
                self.page.open(ft.SnackBar(ft.Text("Could not generate chart (no data?)")))
            
            self.page.update()
        except Exception as ex:
            print(f"Error opening Gantt browser: {ex}")
            self.page.open(ft.SnackBar(ft.Text(f"Error opening chart: {str(ex)}")))
            self.page.update()

    def open_column_selector(self, e):
        # Define all available columns for this view
        all_columns = [
            "Task ID", "Task Name", "Resource", "Start", "End", "%", "Workstream", "Actions"
        ]
        page = self.page if self.page else self.custom_page
        if page:
            try:
                show_column_selector_dialog(page, "Project Plan", all_columns, self.load_data)
            except Exception as ex:
                print(f"Error showing column selector: {ex}")
                if page:
                    page.open(ft.SnackBar(ft.Text(f"Error: {str(ex)}")))
        else:
            print("Error: No page found for column selector")


    def load_data(self):
        if not self.page: return

        project_id = self.page.session.get("project_id")
        
        # Apply Heading Color handled by render_header


        # 1. Fetch Data
        tasks = []
        try:
            from database import get_db_context
            with get_db_context() as db:
                if project_id:
                     tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
                     db.expunge_all() # Detach from session
                else:
                    # Portfolio View: Projects become Tasks
                    projects = db.query(Project).all()
                    for p in projects:
                        p_tasks = db.query(ProjectTask).filter(ProjectTask.project_id == p.id).all()
                        p_start = min([t.start_date for t in p_tasks if t.start_date], default=None)
                        p_end = max([t.end_date for t in p_tasks if t.end_date], default=None)
                        
                        comps = [t.completion for t in p_tasks if t.completion is not None]
                        avg_comp = int(sum(comps) / len(comps)) if comps else 0
                        
                        class VirtualTask: pass
                        vt = VirtualTask()
                        vt.task_id = str(p.id)
                        vt.task_name = p.name
                        vt.resource = "Project"
                        vt.start_date = p_start if p_start else ""
                        vt.end_date = p_end if p_end else ""
                        vt.completion = avg_comp
                        vt.workstream = p.status
                        tasks.append(vt)
                        
        except Exception as ex:
             print(f"Error loading data: {ex}")
             self.page.open(ft.SnackBar(ft.Text(f"Error loading data: {ex}")))

        # Sort tasks
        tasks.sort(key=lambda t: get_task_sort_key(t.task_id))

        # 2. Prepare Gantt Content (if needed)
        # We always prepare it if tab is selected, or we could lazy load.
        # For layout consistency, let's prepare it.
        self.gantt_chart_content = None # Reset
        if self.selected_tab_index == 0:
            try:
                chart = None
                if project_id:
                     # Native Project Gantt
                     chart = generate_native_gantt_chart(tasks, view_mode=self.view_mode)
                else:
                     # Native Portfolio Gantt
                     # Need to reconstruct project data dict list expected by util
                     # Or assuming 'tasks' (VirtualTasks) can be used? 
                     # generate_native_portfolio_gantt_chart expects list of dicts: {'name', 'start_date', 'end_date', 'status'}
                     # We have `tasks` as VirtualTasks.
                     projects_data = []
                     for t in tasks:
                         if t.start_date and t.end_date:
                            projects_data.append({
                                'name': t.task_name,
                                'start_date': t.start_date,
                                'end_date': t.end_date,
                                'status': t.workstream 
                            })
                     chart = generate_native_portfolio_gantt_chart(projects_data, view_mode=self.view_mode)

                # Controls Row
                controls_row = ft.Row([
                    ft.ElevatedButton("Open in Browser", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda e: self.open_gantt_browser(e, is_portfolio=not project_id)),
                    ft.Dropdown(
                        value=self.view_mode,
                        options=[ft.dropdown.Option(o) for o in ["Days", "Weeks", "Months", "Quarters", "Years"]],
                        on_change=self.on_view_mode_change,
                        width=150,
                        label="Scale",
                        content_padding=5
                    ),
                ], wrap=True)

                # Chart Row (Scrollable)
                chart_row = ft.Row(
                    [
                        ft.Container(chart if chart else ft.Text("No data for chart"), width=1500)
                    ], 
                    scroll=ft.ScrollMode.ALWAYS,
                    expand=True
                )

                self.gantt_chart_content = ft.Column(
                    [
                        ft.Container(controls_row, padding=ft.padding.only(top=10, bottom=10)),
                        chart_row,
                    ],
                    expand=True,
                    scroll=ft.ScrollMode.AUTO # Vertical scroll for the whole tab if needed
                )
            except Exception as ex:
                self.gantt_chart_content = ft.Text(f"Error generating chart: {ex}")

        # 3. Render
        is_mobile = self.page.width < 800
        self._last_is_mobile = is_mobile # Update tracker
        
        if is_mobile:
             self.render_mobile_view(tasks)
        else:
             self.render_desktop_view(tasks)
        
        self.page.update()

    def render_desktop_view(self, tasks):
        self.content.controls.clear()
        
        # 1. Header using BasePageView
        extra_actions = [
             ft.IconButton(ft.Icons.VIEW_COLUMN, on_click=self.open_column_selector, tooltip="Select Columns", icon_color=ft.Colors.PRIMARY),
             ft.IconButton(ft.Icons.FILTER_LIST, on_click=self.open_filter_dialog, tooltip="Filter Columns", icon_color=ft.Colors.PRIMARY),
             ft.IconButton(ft.Icons.FILE_UPLOAD, on_click=self.import_picker.pick_files, tooltip="Import Tasks", icon_color=ft.Colors.PRIMARY),
             ft.IconButton(ft.Icons.FILE_DOWNLOAD, on_click=self.export_tasks, tooltip="Export Tasks", icon_color=ft.Colors.PRIMARY),
             ft.IconButton(ft.Icons.ADD, on_click=self.open_add_task_dialog, tooltip="Add Task", icon_color=ft.Colors.PRIMARY),
        ]
        
        header_row = self.render_header(extra_actions=extra_actions)

        # 2. Build Task Table Rows
        # Define Columns Configuration
        project_id = self.page.session.get("project_id")
        
        columns_config = [
            ("Task ID", ft.DataColumn(ft.Text("Project ID" if not project_id else "Task ID")), lambda t: ft.DataCell(ft.Row([ft.Container(width=20 * (t.task_id.count('.') if t.task_id else 0)), ft.Text(t.task_id)]))),
            ("Task Name", ft.DataColumn(ft.Text("Project Name" if not project_id else "Task Name")), lambda t: ft.DataCell(ft.Row([ft.Container(width=20 * (t.task_id.count('.') if t.task_id else 0)), ft.Text(t.task_name, tooltip=t.task_name)]))),
            ("Resource", ft.DataColumn(ft.Text("Type" if not project_id else "Resource")), lambda t: ft.DataCell(ft.Text(t.resource))),
            ("Start", ft.DataColumn(ft.Text("Start")), lambda t: ft.DataCell(ft.Text(t.start_date))),
            ("End", ft.DataColumn(ft.Text("End")), lambda t: ft.DataCell(ft.Text(t.end_date))),
            ("%", ft.DataColumn(ft.Text("%")), lambda t: ft.DataCell(ft.Text(str(t.completion)))),
            ("Workstream", ft.DataColumn(ft.Text("Status" if not project_id else "Workstream")), lambda t: ft.DataCell(ft.Text(t.workstream))),
        ]
        
        if project_id: # Only show actions for single project
             columns_config.append(
                ("Actions", ft.DataColumn(ft.Text("Actions")), lambda t: ft.DataCell(ft.Row([
                    ft.IconButton(ft.Icons.PLAYLIST_ADD, icon_color=ft.Colors.GREY if (t.task_id is None or t.task_id.count('.') >= 2) else ft.Colors.GREEN, tooltip="Add Sub-Task", on_click=lambda e, task=t: self.show_task_dialog(parent_task=task), disabled=(t.task_id.count('.') >= 2 if t.task_id else True)),
                    ft.IconButton(ft.Icons.EDIT, icon_color=ft.Colors.BLUE, tooltip="Edit Task", on_click=lambda e, task=t: self.open_edit_task_dialog(task)),
                    ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, tooltip="Delete-Task", on_click=lambda e, task=t: self.delete_task(task)),
                ])))
             )

        # Filter Columns
        default_visible = ["Task ID", "Task Name", "Resource", "Start", "End", "%", "Actions"]
        visible_col_names = get_visible_columns(self.page, "Project Plan", default_visible) if self.page else default_visible
        
        visible_columns = [c[1] for c in columns_config if c[0] in visible_col_names]
        
        # Build Rows
        rows = []
        for t in tasks:
            cells = [c[2](t) for c in columns_config if c[0] in visible_col_names]
            rows.append(ft.DataRow(cells=cells))
            
        # Bind to DataTable
        self.task_table.columns = visible_columns
        self.task_table.rows = rows

        # 3. Gantt Content
        gantt_content = ft.Container(ft.Text("Select Gantt Tab"), padding=20)
        if self.selected_tab_index == 0:
             if hasattr(self, 'gantt_chart_content'):
                 # Wrap chart in scrollable row matchin dashboard logic
                 # Check if self.gantt_chart_content already has the scrollable structure?
                 # In load_data, I wrapped it in ft.Column(ft.Row([...], scroll=...)). 
                 # So it should be fine to drop in.
                 gantt_content = self.gantt_chart_content

        # 4. Tabs
        desktop_tabs = ft.Tabs(
            selected_index=self.selected_tab_index,
            animation_duration=300,
            on_change=self.on_tab_change,
            tabs=[
                 ft.Tab(
                    text="Gantt Chart",
                    icon=ft.Icons.BAR_CHART,
                    content=gantt_content,
                ),
                ft.Tab(
                    text="Task List",
                    icon=ft.Icons.LIST,
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [self.task_table],
                                    scroll=ft.ScrollMode.ALWAYS,
                                ),
                            ],
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        ),
                        expand=True,
                    ),
                )
            ],
            expand=True
        )

        self.content.controls.extend([
            header_row,
            ft.Divider(),
            desktop_tabs
        ])

    def download_template(self, e):
        self.template_picker.save_file(allowed_extensions=["csv"], file_name="task_template.csv")

    def on_template_save_result(self, e: ft.FilePickerResultEvent):
        if e.path:
            try:
                df = generate_template_dataframe()
                df.to_csv(e.path, index=False)
                self.page.open(ft.SnackBar(ft.Text(f"Template saved to {e.path}")))
                self.page.update()
            except Exception as ex:
                self.page.open(ft.SnackBar(ft.Text(f"Error saving template: {str(ex)}")))
                self.page.update()

    def on_import_result(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return
        
        project_id = self.page.session.get("project_id")
        if not project_id:
            self.page.open(ft.SnackBar(ft.Text("Please select a project first")))
            self.page.update()
            return

        file = e.files[0]
        try:
            with open(file.path, "rb") as f:
                content = f.read()
            
            success, message = import_tasks_from_file(project_id, content, file.name)
            
            if success:
                self.page.open(ft.SnackBar(ft.Text(f"Import successful: {message}")))
                self.load_data()
            else:
                self.page.open(ft.SnackBar(ft.Text(f"Import failed: {message}")))
            self.page.update()
        except Exception as ex:
            self.page.open(ft.SnackBar(ft.Text(f"Error reading file: {str(ex)}")))
            self.page.update()

    def export_tasks(self, e):
        project_id = self.page.session.get("project_id")
        if not project_id:
            self.page.open(ft.SnackBar(ft.Text("Please select a project first")))
            self.page.update()
            return
        self.export_picker.save_file(allowed_extensions=["csv"], file_name="project_tasks.csv")

    def on_export_save_result(self, e: ft.FilePickerResultEvent):
        if e.path:
            project_id = self.page.session.get("project_id")
            try:
                output = export_tasks_to_file(project_id, "csv")
                with open(e.path, "wb") as f:
                    f.write(output.getvalue())
                self.page.open(ft.SnackBar(ft.Text(f"Tasks exported to {e.path}")))
                self.page.update()
            except Exception as ex:
                self.page.open(ft.SnackBar(ft.Text(f"Error exporting tasks: {str(ex)}")))
                self.page.update()

    def open_add_task_dialog(self, e):
        self.show_task_dialog()

    def open_edit_task_dialog(self, task):
        self.show_task_dialog(task)
        self.page.update()

    def delete_task(self, task):
        page = self.page if self.page else self.custom_page
        if not page:
             print("Error: No page found for delete_task")
             return

        from database import get_db_context
        with get_db_context() as db:
            try:
                task_to_delete = db.get(ProjectTask, task.id)
                if task_to_delete:
                    db.delete(task_to_delete)
                    db.commit()
                else:
                     page.open(ft.SnackBar(ft.Text("Task not found")))
                     return
                self.load_data()
                page.open(ft.SnackBar(ft.Text("Task deleted successfully")))
                page.update()
            except Exception as e:
                db.rollback()
                page.open(ft.SnackBar(ft.Text(f"Error deleting task: {str(e)}")))
                page.update()

    def show_task_dialog(self, task=None, parent_task=None):
        page = self.page if self.page else self.custom_page
        
        # Session access might need page check too, but session is usually on page
        if not page:
             print("Error: No page found for show_task_dialog")
             return

        project_id = page.session.get("project_id")
        if not project_id:
            page.open(ft.SnackBar(ft.Text("Please select a project first")))
            page.update()
            return

        # Defaults
        default_id = "TASK"
        default_start = datetime.now().strftime("%Y-%m-%d")
        default_end = datetime.now().strftime("%Y-%m-%d")
        min_start_date = datetime(2020, 1, 1)

        if parent_task:
            from database import get_db_context
            with get_db_context() as db:
                try:
                    fresh_parent = db.get(ProjectTask, parent_task.id)
                    if fresh_parent:
                         parent_task = fresh_parent # Refresh object
                         # Pre-generate sub-task ID
                         default_id = generate_subtask_id(db, project_id, parent_task.task_id)
                         default_start = parent_task.start_date
                         default_end = parent_task.end_date
                         try:
                             min_start_date = datetime.strptime(parent_task.start_date, "%Y-%m-%d")
                         except:
                             pass
                except Exception:
                    pass
        
        # --- FormBuilder Setup ---
        from utils_forms import FormBuilder
        
        # 1. Define Custom Render Hooks & Config
        
        def render_task_id(col, item):
            val = item.task_id if item else default_id
            return ft.TextField(label="Task ID", value=val, hint_text="Leave as 'TASK' to auto-generate", expand=True, read_only=(parent_task is not None))

        def render_date_field(col, item):
            label = col.name.replace("_", " ").title()
            val = getattr(item, col.name) if item else (default_start if col.name == 'start_date' else default_end)
            
            # Constraints
            first_date = min_start_date if col.name == 'start_date' else datetime(2020, 1, 1)
            
            tf = ft.TextField(label=label, value=val, read_only=True, expand=True)
            
            def on_date_change(e):
                 if e.control.value:
                     tf.value = e.control.value.strftime('%Y-%m-%d')
                     tf.update()
            
            picker = ft.DatePicker(
                first_date=first_date, 
                last_date=datetime(2030, 12, 31),
                on_change=on_date_change
            )
            self.page.overlay.append(picker) # Ensure picker is overlayed
            
            return ft.Row([
                tf,
                ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=lambda e: self.page.open(picker))
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

        def get_date_value(control):
             # Control is Row([TextField, IconButton])
             return control.controls[0].value

        def render_completion(col, item):
            val = (item.completion or 0) if item else 0
            
            # Check children (logic copied from original)
            has_children = False
            if item:
                 from database import get_db_context
                 with get_db_context() as db:
                     t_check = db.get(ProjectTask, item.id)
                     if t_check and t_check.children: has_children = True
            
            slider = ft.Slider(min=0, max=100, divisions=100, value=val, label="{value}%", expand=True, disabled=has_children)
            inp = ft.TextField(value=str(val), width=60, suffix_text="%", read_only=has_children)
            
            if has_children:
                slider.tooltip = "Calculated from sub-tasks"
                inp.tooltip = "Calculated from sub-tasks"

            def on_slider(e):
                inp.value = str(int(e.control.value))
                inp.update()
            
            def on_input(e):
                try:
                    v = int(e.control.value)
                    if 0 <= v <= 100:
                        slider.value = v
                        slider.update()
                except: pass
            
            slider.on_change = on_slider
            inp.on_change = on_input
            
            return ft.Row([slider, inp], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        def get_completion_value(control):
             # Control is Row([Slider, TextField])
             # Return int from slider
             return int(control.controls[0].value)


        field_config = {
            'task_id': { 'render': render_task_id },
            'task_name': { 'label': 'Task Name' }, # Standard but explicit
            'start_date': { 'render': render_date_field, 'get_value': get_date_value },
            'end_date': { 'render': render_date_field, 'get_value': get_date_value },
            'completion': { 'render': render_completion, 'get_value': get_completion_value },
            'workstream': { 'read_only': True } if parent_task else {}
        }
        
        # Instantiate Builder
        fb = FormBuilder(self.page, ProjectTask, item=task, field_config=field_config)
        fields = fb.build_fields()



        # Sub-task list (if editing existing task)
        subtask_column = ft.Column()
        if task:
             subtask_column.controls.append(ft.Text("Sub-Tasks", weight=ft.FontWeight.BOLD))
             # We need to query fresh children
             from database import get_db_context
             with get_db_context() as db:
                 try:
                     fresh_task = db.get(ProjectTask, task.id)
                     if fresh_task and fresh_task.children:
                         for child in fresh_task.children:
                             subtask_column.controls.append(
                                 ft.Row([
                                     ft.Text(f"{child.task_id}: {child.task_name}"),
                                     ft.IconButton(ft.Icons.EDIT, icon_size=16, on_click=lambda e, t=child: (self.page.close(dialog), self.show_task_dialog(t)))
                                 ])
                             )
                 except Exception:
                     pass
             
             subtask_column.controls.append(
                 ft.ElevatedButton("Add Sub-Task", icon=ft.Icons.ADD, on_click=lambda e: (self.page.close(dialog), self.show_task_dialog(parent_task=task)), disabled=(task.task_id.count('.') >= 2))
             )

        def finalize_save(values):
             from database import get_db_context
             with get_db_context() as db:
                 try:
                     current_task_id = values['task_id']
                     if current_task_id == "TASK": current_task_id = ""
                     
                     # Task ID Uniqueness Check (Re-check in write session)
                     if task:
                            t = db.get(ProjectTask, task.id)
                            if not t:
                                 self.page.open(ft.SnackBar(ft.Text("Task not found (concurrent delete?)")))
                                 return

                            if current_task_id and current_task_id != t.task_id:
                                 existing = db.query(ProjectTask).filter(ProjectTask.project_id == project_id, ProjectTask.task_id == current_task_id).first()
                                 if existing:
                                    task_id_field.error_text = "Task ID already exists"
                                    task_id_field.update()
                                    return
                            
                            t.task_id = current_task_id if current_task_id else t.task_id 
                            if not t.task_id:
                                t.task_id = generate_task_id(db, project_id)



                            t.task_name = values['task_name']
                            t.resource = values['resource']
                            t.workstream = values['workstream']
                            t.start_date = values['start_date']
                            t.end_date = values['end_date']
                            t.completion = values['completion']
                            
                            # Update hierarchy
                            if t.parent:
                                 update_hierarchy_dates(db, t)
                                 update_parent_completion(db, t.parent)

                     else:
                            # Create New
                            final_task_id = current_task_id
                            if not final_task_id:
                                final_task_id = generate_task_id(db, project_id)
                            else:
                                existing = db.query(ProjectTask).filter(ProjectTask.project_id == project_id, ProjectTask.task_id == final_task_id).first()
                                if existing:
                                    task_id_field.error_text = "Task ID already exists in this project"
                                    task_id_field.update()
                                    return
                            
                            # Handle Parent
                            p_id = None
                            if parent_task:
                                 p_id = parent_task.id
                            elif final_task_id and "." in final_task_id:
                                 parent_id_str = final_task_id.rsplit(".", 1)[0]
                                 p_obj = db.query(ProjectTask).filter(ProjectTask.project_id == project_id, ProjectTask.task_id == parent_id_str).first()
                                 if p_obj: p_id = p_obj.id

                            new_task = ProjectTask(
                                project_id=project_id,
                                task_id=final_task_id,
                                task_name=values['task_name'],
                                resource=values['resource'],
                                workstream=values['workstream'],
                                start_date=values['start_date'],
                                end_date=values['end_date'],
                                completion=values['completion'],
                                parent_id=p_id
                            )
                            db.add(new_task)
                            db.flush() 
                            
                            if p_id:
                                p_obj_ref = db.get(ProjectTask, p_id)
                                update_hierarchy_dates(db, new_task)
                                update_parent_completion(db, p_obj_ref)

                     db.commit()
                     self.load_data()
                     self.page.close(dialog)
                     self.page.open(ft.SnackBar(ft.Text("Task saved successfully")))
                     self.page.update()

                 except Exception as ex:
                     db.rollback()
                     print(f"Save error: {ex}")
                     self.page.open(ft.SnackBar(ft.Text(f"Error saving task: {str(ex)}")))
                     self.page.update()

        def save_task(e):
            # 1. Gather Values
            try:
                 values = fb.get_data()
            except Exception as ex:
                 self.page.open(ft.SnackBar(ft.Text(f"Error reading form: {ex}")))
                 self.page.update()
                 return

            if not values.get('task_name'):
                fb.controls['task_name'].error_text = "Task Name is required"
                fb.controls['task_name'].update()
                return
            
            # 2. Validation (Format)
            import re
            current_task_id = values['task_id']
            if current_task_id == "TASK": current_task_id = "" # Ignore placeholder
            
            if current_task_id:
                if not re.match(r"^TASK\d+(\.\d+)*$", current_task_id):
                    # fb.controls['task_id'] is the TextField
                    fb.controls['task_id'].error_text = "Invalid format. Use TASKX or TASKX.Y"
                    fb.controls['task_id'].update()
                    return
            
            # Start > End Check
            if values['start_date'] and values['end_date']:
                try:
                    s_d = datetime.strptime(values['start_date'], "%Y-%m-%d") if isinstance(values['start_date'], str) else values['start_date']
                    e_d = datetime.strptime(values['end_date'], "%Y-%m-%d") if isinstance(values['end_date'], str) else values['end_date']
                    # Ensure both are dates
                    if isinstance(s_d, datetime): s_d = s_d.date()
                    if isinstance(e_d, datetime): e_d = e_d.date()
                    
                    if s_d > e_d:
                        self.page.open(ft.SnackBar(ft.Text("Error: Start Date cannot be after End Date")))
                        self.page.update()
                        return
                except ValueError:
                    pass
            
            # 3. Check Parent Constraints (Date Extension)
            from database import get_db_context
            with get_db_context() as db_check:
                needs_confirm = False
                p_end_date = None
                
                try:
                    p_obj = None
                    if parent_task:
                        p_obj = db_check.get(ProjectTask, parent_task.id)
                    elif current_task_id and "." in current_task_id:
                         parent_id_str = current_task_id.rsplit(".", 1)[0]
                         p_obj = db_check.query(ProjectTask).filter(ProjectTask.project_id == project_id, ProjectTask.task_id == parent_id_str).first()
                         if not p_obj and not parent_task:
                             # Wait, if manual entry and parent not found
                             fb.controls['task_id'].error_text = f"Parent task '{parent_id_str}' does not exist."
                             fb.controls['task_id'].update()
                             return
                    
                    if p_obj:
                         p_end_date = p_obj.end_date
                         try:
                            p_end = datetime.strptime(p_obj.end_date, "%Y-%m-%d")
                            c_end_str = values['end_date'] 
                            c_end = datetime.strptime(c_end_str, "%Y-%m-%d")
                            if c_end > p_end:
                                needs_confirm = True
                         except: pass
                except Exception:
                     pass

            if needs_confirm:
                def confirm_extend(e):
                    self.page.close(confirm_dialog)
                    finalize_save(values)
                    
                confirm_dialog = ft.AlertDialog(
                    title=ft.Text("Extend Parent Task?"),
                    content=ft.Text(f"The end date ({values['end_date']}) is after the parent task's end date ({p_end_date}).\nThis will extend the parent task."),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda e: self.page.close(confirm_dialog)),
                        ft.ElevatedButton("Proceed", on_click=confirm_extend)
                    ]
                )
                self.page.open(confirm_dialog)
            else:
                finalize_save(values)




            



                







                    


        # Layout
        form_rows = []
        for f in fields:
             form_rows.append(ft.Column([f], col={"sm": 12, "md": 6}))

        dialog_content = ft.Container(
            content=ft.Column(
                [
                    ft.ResponsiveRow(
                        form_rows + [ft.Column([ft.Divider(), subtask_column], col=12)],
                        run_spacing=10,
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
            width=800,
            padding=10
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Edit Task" if task else ("Add Sub-Task" if parent_task else "Add Task")),
            content=dialog_content,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.page.close(dialog)),
                ft.ElevatedButton("Save", on_click=save_task),
            ],
        )

        target_page = self.page if self.page else self.custom_page
        if target_page:
            target_page.open(dialog)
            target_page.update()
        else:
            print("Error: No page found to open dialog")



