import flet as ft
from database import get_db_context
from models import Project
from config import AppConfig
from utils import get_settings

class BasePageView(ft.Container):
    """
    Base class for all application views.
    Handles:
    - Common layout (Header, Divider, Content Area)
    - Project context (Dropdown, Session update)
    - Theme application (Heading colors)
    - Resize handling
    """
    def __init__(self, page, title, icon=None, enable_project_filter=True):
        super().__init__(expand=True, padding=20, alignment=ft.alignment.top_left)
        self.page = page
        self.title = title
        self.icon = icon
        self.enable_project_filter = enable_project_filter
        
        self.title_text = ft.Text(title, size=24, weight=ft.FontWeight.BOLD)
        
        # Init Project Dropdown
        self.project_dropdown = None
        if self.enable_project_filter:
            self.project_dropdown = ft.Dropdown(
                label="Select Project",
                width=300,
                on_change=self.on_project_change,
                border_color="blue", # Default, updated by theme
                text_size=14,
                content_padding=10,
            )
        
        # Main Content container (subclasses populate this)
        self.content_area = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        
        # Set self.content to the basic structure. 
        # Subclasses can append to controls or work with layouts inside content_area.
        # But BaseLogView uses self.content.controls = [...] which overwrites everything.
        # To avoid confusion, we can let subclasses define the structure OR we enforce it here.
        # Enforcing is DRYer.
        # Structure: Header -> Divider -> ContentArea
        
        # NOTE: Subclasses like `BaseLogView` override `render_*` and currently overwrite `self.content.controls`.
        # We need to change that pattern in the subclasses to use `self.content_area`.
        
        self.content = ft.Column(
             controls=[
                # Header will be injected by render_header()
                ft.Container(), 
                # Content
                self.content_area
             ],
             expand=True
        )

        # Initial Project Load
        if self.enable_project_filter:
            self.load_projects()
        
        # Resize Handler
        self.page.on_resized = self.handle_resize

    def handle_resize(self, e):
        # Override in subclass to refresh content
        pass
        
    def on_project_change(self, e):
        if not self.enable_project_filter: return
        val = self.project_dropdown.value
        if val == "all":
            self.page.session.set("project_id", None)
        else:
            self.page.session.set("project_id", int(val))
        
        # Trigger data reload in subclass
        if hasattr(self, 'load_data'):
            self.load_data()
        else:
            self.handle_resize(None) # Fallback

    def load_projects(self):
        try:
            with get_db_context() as db:
                projects = db.query(Project).all()
            
            self.project_dropdown.options = [ft.dropdown.Option(key="all", text="All Projects")] + [
                ft.dropdown.Option(key=str(p.id), text=p.name) for p in projects
            ]
            
            # Set default from session
            current_project_id = self.page.session.get("project_id")
            if current_project_id:
                self.project_dropdown.value = str(current_project_id)
            else:
                self.project_dropdown.value = "all"
            
            self.apply_theme()
            
        except Exception as e:
            print(f"ERROR in load_projects: {e}")
            self.project_dropdown.options = []
            self.project_dropdown.error_text = "Failed to load projects"

    def apply_theme(self):
        settings = get_settings(self.page)
        heading_color = settings.get("heading_color", "blue")
        
        self.title_text.color = heading_color
        if self.project_dropdown:
            self.project_dropdown.label_style = ft.TextStyle(color=heading_color)
            self.project_dropdown.border_color = heading_color

    def render_header(self, extra_actions=[]):
        """
        Returns a standardised User Interface Header Row.
        extra_actions: list of controls to add to the right side (Buttons, etc)
        """
        settings = get_settings(self.page)
        heading_color = settings.get("heading_color", "blue")
        
        # Ensure title color is updated (in case apply_theme wasn't called recently)
        self.title_text.color = heading_color
        
        # Icon
        icon_control = ft.Icon(self.icon, size=30, color=heading_color) if self.icon else ft.Container()
        
        is_mobile = self.page.width < 768 if self.page else False

        if is_mobile:
             # Stacked Layout for Mobile
             if self.project_dropdown:
                 self.project_dropdown.width = None # Allow full width
             
             actions_content = []
             if self.enable_project_filter:
                 actions_content.append(self.project_dropdown)
             
             if extra_actions:
                 # Add buttons in a wrapped row
                 actions_content.append(
                     ft.Row(extra_actions, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True)
                 )
             
             return ft.Column([
                 ft.Row([icon_control, self.title_text], alignment=ft.MainAxisAlignment.CENTER),
                 ft.Container(height=5),
                 ft.Column(actions_content, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                 ft.Divider()
             ])
        else:
             # Desktop Layout
             if self.project_dropdown:
                 self.project_dropdown.width = 300
             
             actions_content = [
                ft.Container(self.project_dropdown, height=70, padding=ft.padding.only(top=10)) if self.enable_project_filter else ft.Container()
             ] + extra_actions

             return ft.Column([
                ft.Row(
                    [
                        ft.Row([icon_control, self.title_text]),
                        ft.Row(actions_content, alignment=ft.MainAxisAlignment.END)
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                ft.Divider()
            ])

