import flet as ft
from sqlalchemy.orm import Session
from database import get_db
from models import User
from utils import get_settings

class LoginView(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.alignment = ft.alignment.center
        self.expand = True
        
        # Logo
        self.logo = ft.Image(src="/logo_new_1.png", width=150, height=150, fit=ft.ImageFit.CONTAIN, border_radius=ft.border_radius.all(25))
        
        # Title
        self.title = ft.Text("CARDI Log", size=30, weight=ft.FontWeight.BOLD)
        
        # Fields
        self.username_field = ft.TextField(label="Username", width=300, on_submit=self.login, autofocus=True)
        self.password_field = ft.TextField(label="Password", password=True, can_reveal_password=True, width=300, on_submit=self.login)
        self.error_text = ft.Text("", color=ft.Colors.RED)
        
        # Login Button
        self.login_button = ft.ElevatedButton(
            text="Login",
            width=300,
            on_click=self.login
        )
        
        # Card Content
        self.content = ft.Container(
            content=ft.Column(
                [
                    self.logo,
                    self.title,
                    ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                    self.username_field,
                    self.password_field,
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    self.error_text,
                    self.login_button
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10
            ),
            padding=40,
            border_radius=10,
        )

    def login(self, e):
        username = self.username_field.value
        password = self.password_field.value
        
        if not username or not password:
            self.error_text.value = "Please enter both username and password"
            self.error_text.update()
            return

        from database import get_db_context
        try:
            with get_db_context() as db:
                user = db.query(User).filter(User.username == username).first()
                if user and user.check_password(password):
                    # Login Success
                    self.page.session.set("user_id", user.id)
                    self.page.session.set("is_admin", user.is_admin)
                    self.page.go("/")
                else:
                    self.error_text.value = "Invalid username or password"
                    self.error_text.update()
        except Exception as ex:
            self.error_text.value = f"An error occurred: {str(ex)}"
            self.error_text.update()

