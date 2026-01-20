import flet as ft

class MainLayout(ft.Row):
    def __init__(self, page: ft.Page, heading_color: str, drawer_builder, initial_content=None):
        super().__init__(expand=True, spacing=0)
        self.page = page
        self.heading_color = heading_color
        self.drawer_builder = drawer_builder
        
        self.rail = None
        self.divider = ft.VerticalDivider(width=1)
        self.content_area = ft.Container(content=initial_content, expand=True)
        
        self._last_is_mobile = None
        
        # Initial controls structure
        self.controls = [self.content_area]

    def set_rail(self, rail):
        self.rail = rail
        # Reconstruct controls structure
        self.controls = [self.rail, self.divider, self.content_area]
        # Only trigger logic if mounted (has backend ID)
        if self.uid:
             self.handle_resize(None)
             self.update()

    def set_content(self, content):
        self.content_area.content = content
        self.content_area.update()

    def did_mount(self):
        # Attach resize handler when this layout enters the screen
        self.page.on_resized = self.handle_resize
        # Force re-evaluation of resize logic because during init (set_rail), 
        # the View (and AppBar) might not have been available.
        self._last_is_mobile = None
        # Trigger initial check
        self.handle_resize(None)

    def will_unmount(self):
        # Detach handler to prevent memory leaks or phantom calls
        if self.page.on_resized == self.handle_resize:
            self.page.on_resized = None

    def handle_resize(self, e):
        # print("DEBUG: MainLayout.handle_resize called") # Noisy
        if not self.page: return
        is_mobile = self.page.width < 800
        # print(f"DEBUG: MainLayout resize - Width: {self.page.width}, IsMobile: {is_mobile}, Last: {self._last_is_mobile}")
        
        # Debounce/State Check
        if is_mobile == self._last_is_mobile: return
        print(f"DEBUG: MainLayout State Change - IsMobile: {is_mobile}")
        self._last_is_mobile = is_mobile
        
        # Toggle Sidebar Visibility
        if self.rail: 
            self.rail.visible = not is_mobile
        self.divider.visible = not is_mobile
        
        # Update AppBar (Title & Leading Icon)
        # We assume the AppBar is attached to the top-most view.
        if self.page.views:
            view = self.page.views[-1]
            app_bar = view.appbar
            
            if app_bar:
                if is_mobile:
                    # Mobile Mode: Hamburger + No Title
                    app_bar.leading = ft.IconButton(
                        ft.Icons.MENU, 
                        on_click=lambda e: self.open_drawer(),
                        icon_color=self.heading_color,
                        tooltip="Menu"
                    )
                    app_bar.title = ft.Container()
                    
                    # Ensure drawer is set
                    if not self.page.drawer:
                         self.page.drawer = self.drawer_builder()
                    # View-specific drawer reference helps some Flet versions
                    view.drawer = self.page.drawer
                else:
                    # Desktop Mode: No Hamburger + Title
                    app_bar.leading = None
                    app_bar.title = ft.Text("CARDI Log", color=self.heading_color, size=20, weight=ft.FontWeight.BOLD)
                    self.page.drawer = None
                    view.drawer = None
                
                app_bar.update()

        # Broadcast resize to content if supported
        if self.content_area.content and hasattr(self.content_area.content, "handle_resize"):
             try:
                 self.content_area.content.handle_resize(e)
             except Exception as ex:
                 print(f"Error checking content resize: {ex}")

        if self.uid:
            self.update()

    def open_drawer(self):
        if self.page.drawer:
            self.page.open(self.page.drawer)

