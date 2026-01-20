import flet as ft
import logging
import traceback
import os
import sys
import time

# Setup logging to catch crashes
def setup_logging():
    try:
        # Try finding a writable directory
        # On Android, HOME or TEMP are usually set to writable app-specific dirs
        log_dir = os.environ.get("TEMP", os.environ.get("HOME", os.path.expanduser("~")))
        log_file = os.path.join(log_dir, "cardi_log_debug.txt")
        
        # Check if writable, otherwise fallback to a known writable Android path if possible
        # Or just use the script's dir if not in a frozen APK state (unlikely to be writable in APK)
        
        logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("Application starting (Log file initialized)...")
    except Exception as e:
        # If we can't write to a file, just log to console (which Flet captures in some builds)
        logging.basicConfig(level=logging.DEBUG, 
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.error(f"Could not initialize log file at {log_file if 'log_file' in locals() else 'unknown'}: {e}")

setup_logging()

def main(page: ft.Page):
    # --- 0. Diagnostics (for APK debugging) ---
    diag_str = ""
    app_root = os.path.dirname(os.path.abspath(__file__))
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    
    diag_str += f"App Root: {app_root}\n"
    diag_str += f"Current Directory: {os.getcwd()}\n"
    
    # --- 0.1 SELF-FIX FOR MANGLED PATHS (Android Build Tool Bug) ---
    # The build process sometimes flattens folders into filenames containing backslashes.
    # We detect these and restore the actual directory structure.
    try:
        items_to_fix = [i for i in os.listdir(app_root) if "\\" in i]
        if items_to_fix:
            logging.info(f"Detected {len(items_to_fix)} mangled paths. Fixing...")
            for item in items_to_fix:
                parts = item.split("\\")
                current_dir = app_root
                for part in parts[:-1]:
                    current_dir = os.path.join(current_dir, part)
                    if not os.path.exists(current_dir):
                        os.makedirs(current_dir)
                
                old_path = os.path.join(app_root, item)
                new_path = os.path.join(app_root, *parts)
                os.rename(old_path, new_path)
            logging.info("FileSystem Fix Complete.")
        else:
            logging.info("No mangled paths detected.")
    except Exception as fix_e:
        logging.error(f"FileSystem Fixer failed: {fix_e}")

    logging.info(diag_str)

    # --- 1. Immediate Splash Screen Setup ---
    page.title = "CARDI Log"
    page.window.icon = "/favicon.ico" 
    page.favicon = "/favicon.ico" 
    page.padding = 0

    # Flet to show window immediately.
    # Splash UI Components
    pb = ft.ProgressBar(width=200, color="amber", bgcolor="#222222")
    loading_text = ft.Text("Initializing...", color=ft.Colors.GREY, size=12)
    
    splash_view = ft.View(
        "/splash",
        [
            ft.Image(src="/logo_new_1.png", width=300, height=300, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(25)),
            ft.Container(height=20),
            loading_text,
            ft.Container(content=pb, width=200),
        ],
        padding=0,
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER
    )
    
    page.views.append(splash_view)
    page.update()
    
    # --- 2. Lazy Load Imports & Initialization ---
    try:
        # Load heavy database modules
        logging.info("Loading Data Layer...")
        loading_text.value = "Connecting to Database..."
        pb.value = 0.2
        page.update()
        
        from database import engine, Base, get_db, get_db_context
        import models
        from models import User, RiskLog, IssuesLog, ActionsLog, DADLog, ChangeLog, ProjectTask
        
        # Ensure tables exist
        logging.info("Creating database tables if needed...")
        Base.metadata.create_all(bind=engine)
        logging.info("Database initialized.")

        # Load utils
        loading_text.value = "Loading Utilities..."
        pb.value = 0.4
        page.update()
        from utils import get_settings, save_settings

        # Load views (includes heavy pandas/plotly/seaborn imports via dashboard/utils_data)
        logging.info("Loading Views...")
        loading_text.value = "Loading Interface Components (this may take a moment)..."
        pb.value = 0.6
        page.update()
        
        from app_views.dashboard import DashboardView
        from app_views.project_view import ProjectView
        from app_views.risk_log import RiskLogView
        from app_views.issue_log import IssueLogView
        from app_views.action_log import ActionLogView
        from app_views.dad_log import DADLogView
        from app_views.change_log import ChangeLogView
        from app_views.project_plan import ProjectPlanView
        from app_views.settings import SettingsView
        from app_views.login import LoginView
        from app_views.admin import AdminView
        from app_views.layout import MainLayout
        
        loading_text.value = "Finalizing..."
        pb.value = 0.9
        page.update()

    except Exception as e:
        logging.critical("Fatal startup error", exc_info=True)
        loading_text.value = "Startup Failed"
        loading_text.color = "red"
        
        error_details = ft.Column([
            ft.Text(f"Error: {str(e)}", color="red", weight="bold", size=16),
            ft.Divider(),
            ft.Text("Diagnostic Information:", weight="bold"),
            ft.Text(diag_str, size=10, font_family="monospace", selectable=True),
            ft.Divider(),
            ft.Text("Traceback:", weight="bold"),
            ft.Text(traceback.format_exc(), size=10, font_family="monospace", selectable=True),
        ], scroll=ft.ScrollMode.AUTO, expand=True)
        
        page.views.clear()
        page.views.append(ft.View("/error", [
            ft.Container(
                content=error_details,
                padding=20,
                expand=True
            )
        ]))
        page.update()
        return

    # --- 3. App Configuration (Post-Load) ---
    p = page
    
    # Load Settings
    settings = get_settings(page)
    heading_color = settings.get("heading_color", "blue")
    
    # FORCE DEFAULT TO DARK (Override any saved 'light' preference)
    if settings.get("theme_mode") != "dark":
        settings["theme_mode"] = "dark"
        save_settings(page, settings)
        
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=settings.get("seed_color", "blue"))
    page.adaptive = True

    # Check/Create Default Admin
    with get_db_context() as db:
        if not db.query(User).first():
            print("Creating default admin user...")
            admin = User(username="admin", is_admin=True)
            admin.set_password("password123")
            db.add(admin)
            db.commit()
    
    # Initialize Views
    # Views initialized per route to ensure fresh state


    def change_view(e):
        selected_index = e.control.selected_index
        if selected_index == 0:
            page.go("/")
        elif selected_index == 1:
            page.go("/projects")
        elif selected_index == 2:
            page.go("/plan")
        elif selected_index == 3:
            page.go("/risks")
        elif selected_index == 4:
            page.go("/issues")
        elif selected_index == 5:
            page.go("/actions")
        elif selected_index == 6:
            page.go("/dads")
        elif selected_index == 7:
            page.go("/changes")
        elif selected_index == 8:
            page.go("/admin")

    def get_destinations():
        return [
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD_OUTLINED, 
                selected_icon=ft.Icons.DASHBOARD, 
                label="Dashboard"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.ACCOUNT_TREE_OUTLINED, 
                selected_icon=ft.Icons.ACCOUNT_TREE, 
                label="Projects"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.CALENDAR_MONTH_OUTLINED, 
                selected_icon=ft.Icons.CALENDAR_MONTH, 
                label="Project Plan"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.WARNING_AMBER_OUTLINED, 
                selected_icon=ft.Icons.WARNING, 
                label="Risk Log"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.ERROR_OUTLINE, 
                selected_icon=ft.Icons.ERROR, 
                label="Issue Log"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.TASK_ALT, 
                selected_icon=ft.Icons.TASK, 
                label="Action Log"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.LIST_ALT_OUTLINED, 
                selected_icon=ft.Icons.LIST_ALT, 
                label="DAD Log"
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.CHANGE_CIRCLE_OUTLINED, 
                selected_icon=ft.Icons.CHANGE_CIRCLE, 
                label="Change Log"
            ),
        ]

    def get_nav_rail(selected_index):
        return ft.NavigationRail(
            selected_index=selected_index,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=400,
            group_alignment=-0.9,
            destinations=get_destinations(),
            on_change=change_view,
        )

    def get_nav_bar(selected_index):
        return ft.NavigationBar(
            selected_index=selected_index,
            destinations=get_destinations(),
            on_change=change_view,
        )

    def open_settings(e):
        page.go("/settings")

    def open_help(e):
        try:
            # Use safe path resolution
            base_dir = os.path.dirname(__file__)
            manual_path = os.path.join(base_dir, "assets", "user_manual.md")
            with open(manual_path, "r") as f:
                full_text = f.read()
        except FileNotFoundError:
            full_text = "## Error\nUser manual not found."

        # Parse sections based on "## "
        sections = []
        lines = full_text.split('\n')
        current_title = "Overview"
        current_content = []
        
        for line in lines:
            if line.startswith("## "):
                # Save previous section
                if current_content or current_title != "Overview":
                    sections.append((current_title, "\n".join(current_content)))
                
                # Start new section
                current_title = line.replace("## ", "").strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Append last section
        if current_content:
             sections.append((current_title, "\n".join(current_content)))

        # Create Tabs
        help_tabs = []
        for title, content in sections:
            # Map titles to icons (optional, basic mapping)
            icon = ft.Icons.ARTICLE
            if "Getting Started" in title: icon = ft.Icons.START
            elif "Navigation" in title: icon = ft.Icons.MAP
            elif "Projects" in title: icon = ft.Icons.ACCOUNT_TREE
            elif "Plan" in title: icon = ft.Icons.CALENDAR_MONTH
            elif "Logs" in title: icon = ft.Icons.LIST_ALT
            elif "Settings" in title: icon = ft.Icons.SETTINGS
            elif "Admin" in title: icon = ft.Icons.ADMIN_PANEL_SETTINGS
            
            help_tabs.append(
                ft.Tab(
                    text=title,
                    icon=icon,
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Markdown(
                                    content, 
                                    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                                    selectable=True,
                                    on_tap_link=lambda e: page.launch_url(e.data) if e.data and e.data.startswith("http") else None
                                )
                            ],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        padding=10
                    )
                )
            )

        dialog = ft.AlertDialog(
            title=ft.Text("User Manual"),
            content=ft.Container(
                content=ft.Tabs(
                    selected_index=0,
                    animation_duration=300,
                    tabs=help_tabs,
                    expand=True,
                    scrollable=True,
                ),
                width=800,
                height=600,
            ),
            actions=[ft.TextButton("Close", on_click=lambda e: page.close(dialog))]
        )
        page.open(dialog)

    def open_about(e):
        # Left Column: Identity
        left_col = ft.Column(
            [
                ft.Image(src="/logo_new_1.png", width=120, height=120, fit=ft.ImageFit.CONTAIN),
                ft.Text("CARDI Log", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("Version 1.0.0", size=16, color=ft.Colors.GREY),
                ft.Container(height=20),
                ft.Text("Licensed under GNU GPLv3", size=12, italic=True),
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=1
        )

        # Right Column: Details & Credits
        right_col = ft.Column(
            [
                ft.Text("Created By", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("Ankit Mittal", size=16),
                ft.TextButton("mr.ankitmittal@gmail.com", on_click=lambda e: page.launch_url("mailto:mr.ankitmittal@gmail.com")),
                ft.TextButton("Author Profile", on_click=lambda e: page.launch_url("https://mgw.dumatics.com/about/index.html")),
                
                ft.Divider(height=20),
                
                ft.Text("Powered By", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("Dumati Consultancy Services Ltd.", size=14),
                ft.TextButton("www.dumatics.com", on_click=lambda e: page.launch_url("https://www.dumatics.com")),
                
                ft.Divider(height=20),
                
                ft.Text("Disclaimer", size=14, weight=ft.FontWeight.BOLD),
                ft.Text("This program comes with ABSOLUTELY NO WARRANTY.", size=10, selectable=True),
                ft.Text("Copyright (C) 2025 Dumati Consultancy Services Ltd.", size=10),
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            expand=1.5,
            scroll=ft.ScrollMode.AUTO
        )

        # Main Layout using ResponsiveRow for Mobile Compatibility
        # Left Col: 4 cols (md), 12 cols (sm)
        # Right Col: 8 cols (md), 12 cols (sm)
        
        content = ft.Container(
            content=ft.Column(
                [
                    ft.ResponsiveRow(
                        [
                            ft.Column([left_col], col={"sm": 12, "md": 4}),
                            ft.Column([right_col], col={"sm": 12, "md": 8}),
                        ],
                        spacing=20,
                        run_spacing=20
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True
            ),
            width=600,
            # height=400, # Height auto
            padding=10
        )

        dialog = ft.AlertDialog(
            title=ft.Text("About CARDI Log"),
            content=content,
            actions=[ft.TextButton("Close", on_click=lambda e: page.close(dialog))],
        )
        page.open(dialog)
        
    def logout(e):
        page.session.clear()
        page.go("/login")

    def open_edit_profile_dialog(e):
        from sqlalchemy.orm import Session
        
        password_field = ft.TextField(label="New Password", password=True, can_reveal_password=True)
        confirm_password_field = ft.TextField(label="Confirm Password", password=True, can_reveal_password=True)
        
        def save_profile(e):
            if not password_field.value:
                password_field.error_text = "Password is required"
                password_field.update()
                return
            if password_field.value != confirm_password_field.value:
                confirm_password_field.error_text = "Passwords do not match"
                confirm_password_field.update()
                return
                
            user_id = page.session.get("user_id")
            if not user_id:
                return

            with get_db_context() as db:
                try:
                    user = db.get(User, user_id)
                    if user:
                        user.set_password(password_field.value)
                        db.commit()
                        page.open(ft.SnackBar(ft.Text("Password updated successfully")))
                        page.close(dialog)
                except Exception as ex:
                    db.rollback()
                    page.open(ft.SnackBar(ft.Text(f"Error updating profile: {str(ex)}")))

        dialog = ft.AlertDialog(
            title=ft.Text("Edit Profile"),
            content=ft.Column(
                [
                    ft.Text("Change Password"),
                    password_field,
                    confirm_password_field
                ],
                tight=True,
                width=400
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.close(dialog)),
                ft.ElevatedButton("Save", on_click=save_profile),
            ],
        )
        page.open(dialog)
        
    def refresh_app(e):
        try:
            # Force reload of current route
            route = page.route
            page.views.clear()
            route_change(route)
            page.update()
        except Exception as ex:
            logging.error(f"Error during refresh: {ex}", exc_info=True)
            page.snack_bar = ft.SnackBar(ft.Text(f"Refresh failed: {ex}"), open=True)
            page.update()

    # Theme Toggle Logic
    def toggle_theme(e):
        page.theme_mode = ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        
        # Update shared settings
        current_settings = get_settings(page)
        current_settings["theme_mode"] = "light" if page.theme_mode == ft.ThemeMode.LIGHT else "dark"
        save_settings(page, current_settings)
        
        # Update icon
        e.control.icon = ft.Icons.DARK_MODE if page.theme_mode == ft.ThemeMode.LIGHT else ft.Icons.LIGHT_MODE
        e.control.tooltip = "Switch to Dark Mode" if page.theme_mode == ft.ThemeMode.LIGHT else "Switch to Light Mode"
        page.update()

    # Determine initial icon based on loaded theme
    initial_theme_icon = ft.Icons.LIGHT_MODE if page.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE
    initial_theme_tooltip = "Switch to Light Mode" if page.theme_mode == ft.ThemeMode.DARK else "Switch to Dark Mode"

    # Navigation Drawer (Mobile)
    def toggle_drawer(e):
        page.drawer.open = True
        page.update()

    # Shared Drawer Destinations
    drawer_destinations = [
        ft.NavigationDrawerDestination(
            icon=ft.Icons.DASHBOARD_OUTLINED, 
            selected_icon=ft.Icons.DASHBOARD, 
            label="Dashboard"
        ),
        ft.NavigationDrawerDestination(
            icon=ft.Icons.ACCOUNT_TREE_OUTLINED, 
            selected_icon=ft.Icons.ACCOUNT_TREE, 
            label="Projects"
        ),
        ft.NavigationDrawerDestination(
            icon=ft.Icons.CALENDAR_MONTH_OUTLINED, 
            selected_icon=ft.Icons.CALENDAR_MONTH, 
            label="Project Plan"
        ),
        ft.NavigationDrawerDestination(
            icon=ft.Icons.WARNING_AMBER_OUTLINED, 
            selected_icon=ft.Icons.WARNING, 
            label="Risk Log"
        ),
        ft.NavigationDrawerDestination(
            icon=ft.Icons.ERROR_OUTLINE, 
            selected_icon=ft.Icons.ERROR, 
            label="Issue Log"
        ),
        ft.NavigationDrawerDestination(
            icon=ft.Icons.TASK_ALT, 
            selected_icon=ft.Icons.TASK, 
            label="Action Log"
        ),
        ft.NavigationDrawerDestination(
            icon=ft.Icons.LIST_ALT_OUTLINED, 
            selected_icon=ft.Icons.LIST_ALT, 
            label="DAD Log"
        ),
        ft.NavigationDrawerDestination(
            icon=ft.Icons.CHANGE_CIRCLE_OUTLINED, 
            selected_icon=ft.Icons.CHANGE_CIRCLE, 
            label="Change Log"
        ),
    ]

    def change_drawer_view(e):
         selected_index = e.control.selected_index
         page.drawer.open = False
         page.update()
         if selected_index == 0: page.go("/")
         elif selected_index == 1: page.go("/projects")
         elif selected_index == 2: page.go("/plan")
         elif selected_index == 3: page.go("/risks")
         elif selected_index == 4: page.go("/issues")
         elif selected_index == 5: page.go("/actions")
         elif selected_index == 6: page.go("/dads")
         elif selected_index == 7: page.go("/changes")

    def create_drawer(selected_index):
        # Helper to create drawer since Layout needs to recreate it if needed
        return ft.NavigationDrawer(
            controls=[
                ft.Container(height=12),
                ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.HEART_BROKEN, color=heading_color, size=30), 
                            ft.Text("CARDI Log", size=24, weight=ft.FontWeight.BOLD)
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Divider()
                ]),
                *drawer_destinations,
                ft.Divider(),
            ],
            on_change=change_drawer_view,
            selected_index=selected_index if selected_index is not None else 0
        )

    def _route_change_impl(route):
        page.views.clear()
        
        # Authentication Check
        user_id = page.session.get("user_id")
        if not user_id and page.route != "/login":
            page.go("/login")
            return
        
        if user_id and page.route == "/login":
            page.go("/")
            return

        if page.route == "/login":
            # Instantiate fresh LoginView
            page.views.append(
                ft.View(
                    "/login",
                    [LoginView(page)],
                    padding=0,
                    vertical_alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                )
            )
            page.update()
            return

        troute = ft.TemplateRoute(page.route)
        
        # Selected Index Logic
        selected_index = 0
        if troute.match("/"): 
            selected_index = 0
        elif troute.match("/projects"): 
            selected_index = 1
        elif troute.match("/plan"): 
            selected_index = 2
        elif troute.match("/risks"): 
            selected_index = 3
        elif troute.match("/issues"): 
            selected_index = 4
        elif troute.match("/actions"): 
            selected_index = 5
        elif troute.match("/dads"): 
            selected_index = 6
        elif troute.match("/changes"): 
            selected_index = 7
        elif troute.match("/admin"): 
            selected_index = None
        elif troute.match("/settings"): 
            selected_index = None

        # Load Settings for Color
        settings = get_settings(page)
        nonlocal heading_color
        heading_color = settings.get("heading_color", "blue")

        # Content Logic
        content = ft.Container()
        if troute.match("/"):
            content = DashboardView(page)
        elif troute.match("/projects"):
            content = ProjectView(page)
        elif troute.match("/plan"):
            content = ProjectPlanView(page)
        elif troute.match("/risks"):
            content = RiskLogView(page)
        elif troute.match("/issues"):
            content = IssueLogView(page)
        elif troute.match("/actions"):
            content = ActionLogView(page)
        elif troute.match("/dads"):
            content = DADLogView(page)
        elif troute.match("/changes"):
            content = ChangeLogView(page)
        elif troute.match("/admin"):
             if not page.session.get("is_admin"):
                 page.go("/")
                 return
             content = AdminView(page)
        elif troute.match("/settings"):
             content = SettingsView()
        
        # Get current user for the menu header
        username = "User"
        if user_id:
            with get_db_context() as db:
                user = db.get(User, user_id)
                if user:
                    username = user.username

        # Profile Menu Items
        def create_menu_item(text, icon, on_click):
            return ft.PopupMenuItem(
                content=ft.Row(
                    [
                        ft.Icon(icon, color=heading_color),
                        ft.Text(text),
                    ]
                ),
                on_click=on_click
            )

        profile_items = [
            ft.PopupMenuItem(text=f"Signed in as {username}", disabled=True),
            ft.PopupMenuItem(), # Divider
            create_menu_item("Edit Profile", ft.Icons.EDIT, open_edit_profile_dialog),
        ]
        
        if page.session.get("is_admin"):
            profile_items.append(
                create_menu_item("User Management", ft.Icons.ADMIN_PANEL_SETTINGS, lambda e: page.go("/admin"))
            )
            
        profile_items.extend([
            create_menu_item("Settings", ft.Icons.SETTINGS, open_settings),
            create_menu_item("Help", ft.Icons.HELP_OUTLINE, open_help),
            create_menu_item("About", ft.Icons.INFO_OUTLINE, open_about),
            ft.PopupMenuItem(), # Divider
            create_menu_item("Logout", ft.Icons.LOGOUT, logout),
        ])


        # App Bar Construction (Initial)
        is_mobile = page.width < 800
        
        app_bar_leading = None
        app_bar_title = None

        if is_mobile:
            app_bar_leading = ft.IconButton(ft.Icons.MENU, on_click=lambda e: page.open(page.drawer), icon_color=heading_color)
            app_bar_title = ft.Container()
        else:
            app_bar_title = ft.Text("CARDI Log", color=heading_color, size=20, weight=ft.FontWeight.BOLD)

        app_bar = ft.AppBar(
            leading=app_bar_leading,
            leading_width=40 if is_mobile else None,
            title=app_bar_title,
            center_title=False,
            bgcolor=None,
            actions=[
                ft.IconButton(
                    icon=initial_theme_icon, 
                    on_click=toggle_theme, 
                    tooltip=initial_theme_tooltip,
                    icon_color=heading_color
                ),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    tooltip="Refresh Page",
                    on_click=refresh_app,
                    icon_color=heading_color
                ),
                ft.PopupMenuButton(
                    content=ft.CircleAvatar(
                        content=ft.Icon(ft.Icons.PERSON),
                        bgcolor=ft.Colors.BLUE_GREY_100,
                        color=ft.Colors.BLACK,
                    ),
                    items=profile_items,
                    tooltip="Profile"
                ),
                ft.Container(width=10) # Padding
            ],
        )

        # MainLayout Instantiation
        # We create a NEW layout for the new View.
        layout = MainLayout(
            page=page, 
            heading_color=heading_color, 
            drawer_builder=lambda: create_drawer(selected_index),
            initial_content=content
        )
        
        # Set Navigation Rail
        layout.set_rail(get_nav_rail(selected_index))

        # Drawer Setup (Initial)
        if is_mobile:
            page.drawer = create_drawer(selected_index)
        else:
            page.drawer = None

        page.views.append(
            ft.View(
                route,
                [
                    layout
                ],
                appbar=app_bar,
                padding=0,
                drawer=page.drawer
            )
        )
        page.update()

    def route_change(route):
        try:
            _route_change_impl(route)
        except Exception as ex:
            print(f"CRITICAL UI ERROR: {ex}") # Console visibility
            logging.error(f"Navigation error: {ex}", exc_info=True)
            page.snack_bar = ft.SnackBar(ft.Text(f"Error loading view: {ex}"), open=True)
            page.update()

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)
        
    # page.on_resized NOT SET here. Handled by MainLayout.did_mount.

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    # Ready to go!
    loading_text.value = "Done!"
    pb.value = 1.0
    page.update()
    time.sleep(0.5)
    
    # Force initial route load (Manual call ensures event fires even if route didn't change from default)
    route_change(page.route)

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
