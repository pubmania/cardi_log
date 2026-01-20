import flet as ft
from utils import get_settings, save_settings

class SettingsView(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        self.padding = 20
        self.alignment = ft.alignment.top_left
        
        self.header_text = ft.Text("Settings", size=30, weight=ft.FontWeight.BOLD)
        self.content = ft.Column(
            [
                self.header_text,
                ft.Divider(),
                self.build_theme_section(),
            ],
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

    def did_mount(self):
        self.load_current_settings()

    def load_current_settings(self):
        # Determine page to use (self.page might be None explicitly in some race conditions?)
        # Use page from get_settings call if possible, or just skip update if no page.
        if not self.page:
            return

        settings = get_settings(self.page)
        
        # Apply Heading Color
        self.header_text.color = settings.get("heading_color", "blue")

        # Theme
        self.theme_switch.value = settings.get("theme_mode", "dark") == "dark"
        self.seed_color_dropdown.value = settings.get("seed_color", "blue")
        self.heading_color_dropdown.value = settings.get("heading_color", "blue")
        
        try:
            self.update()
        except Exception:
            pass

    def save_current_settings(self, e=None):
        page = self.page
        if not page:
            return

        settings = get_settings(page)
        
        # Theme
        settings["theme_mode"] = "dark" if self.theme_switch.value else "light"
        settings["seed_color"] = self.seed_color_dropdown.value
        settings["heading_color"] = self.heading_color_dropdown.value
        
        save_settings(page, settings)
        
        # Apply Theme immediately
        page.theme_mode = ft.ThemeMode.DARK if self.theme_switch.value else ft.ThemeMode.LIGHT
        page.theme = ft.Theme(color_scheme_seed=self.seed_color_dropdown.value)
        
        page.update()
        
        page.open(ft.SnackBar(ft.Text("Settings saved!")))

    def build_theme_section(self):
        self.theme_switch = ft.Switch(label="Dark Mode", on_change=self.save_current_settings)
        
        color_options = [
            ft.dropdown.Option("blue"),
            ft.dropdown.Option("green"),
            ft.dropdown.Option("red"),
            ft.dropdown.Option("purple"),
            ft.dropdown.Option("orange"),
            ft.dropdown.Option("teal"),
            ft.dropdown.Option("pink"),
            ft.dropdown.Option("indigo"),
            ft.dropdown.Option("cyan"),
            ft.dropdown.Option("amber"),
        ]

        self.seed_color_dropdown = ft.Dropdown(
            label="Accent Color",
            options=color_options,
            width=200,
            on_change=self.save_current_settings
        )

        self.heading_color_dropdown = ft.Dropdown(
            label="Heading Color",
            options=color_options,
            width=200,
            on_change=self.save_current_settings
        )
        
        return ft.Column(
            [
                ft.Text("Appearance", size=20, weight=ft.FontWeight.BOLD),
                ft.Row([self.theme_switch]),
                ft.Row([self.seed_color_dropdown, self.heading_color_dropdown]),
            ]
        )

