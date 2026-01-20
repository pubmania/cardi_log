import flet as ft
from .base_log import BaseLogView
from models import User
from utils import get_settings

class AdminView(BaseLogView):
    def __init__(self, page=None):
        # AdminView instantiated in main.py without page usually?
        # main.py: content = AdminView()
        # We need to update main.py for AdminView too if it doesn't pass page.
        
        columns_config = [
            ("id", ft.DataColumn(ft.Text("ID")), lambda i: ft.DataCell(ft.Text(str(i.id)))),
            ("username", ft.DataColumn(ft.Text("Username")), lambda i: ft.DataCell(ft.Text(i.username))),
            ("is_admin", ft.DataColumn(ft.Text("Is Admin")), lambda i: ft.DataCell(
                ft.Icon(ft.Icons.CHECK if i.is_admin else ft.Icons.CLOSE, 
                        color=ft.Colors.GREEN if i.is_admin else ft.Colors.RED)
            )),
        ]
        
        super().__init__(
            page=page, 
            model_class=User, 
            title="User Management", 
            columns_config=columns_config,
            icon=ft.Icons.ADMIN_PANEL_SETTINGS,
            enable_project_filter=False
        )

    def delete_item(self, item):
        if item.username == "admin":
             self.page.open(ft.SnackBar(ft.Text("Cannot delete the default admin user.")))
             self.page.update()
             return

        # Check for last user logic logic requires DB access
        from database import get_db_context
        with get_db_context() as db:
            if db.query(User).count() <= 1:
                self.page.open(ft.SnackBar(ft.Text("Cannot delete the last user.")))
                self.page.update()
                return
        
        super().delete_item(item)

    def show_dialog(self, item=None):
        user = item
        username_field = ft.TextField(label="Username", value=user.username if user else "", expand=True)
        password_field = ft.TextField(label="New Password", password=True, can_reveal_password=True, value="", expand=True) 
        is_admin_checkbox = ft.Checkbox(label="Is Admin", value=user.is_admin if user else False)
        
        if user and user.username == "admin":
            username_field.read_only = True
            is_admin_checkbox.disabled = True

        help_text = "Leave blank to keep existing password." if user else "Required for new users."

        def save_user(e):
            if not username_field.value:
                username_field.error_text = "Username is required"
                username_field.update()
                return
            
            if not user and not password_field.value:
                password_field.error_text = "Password is required for new users"
                password_field.update()
                return

            from database import get_db_context
            with get_db_context() as db:
                try:
                    if user:
                        u = db.get(User, user.id)
                        u.username = username_field.value
                        u.is_admin = is_admin_checkbox.value
                        if password_field.value:
                            u.set_password(password_field.value)
                    else:
                        # Check if username exists
                        existing = db.query(User).filter(User.username == username_field.value).first()
                        if existing:
                            username_field.error_text = "Username already exists"
                            username_field.update()
                            return
                        
                        new_user = User(username=username_field.value, is_admin=is_admin_checkbox.value)
                        new_user.set_password(password_field.value)
                        db.add(new_user)
                    
                    db.commit()
                    self.load_data()
                    self.page.close(dialog)
                    self.page.open(ft.SnackBar(ft.Text("User saved successfully")))
                    self.page.update()
                except Exception as ex:
                    db.rollback()
                    self.page.open(ft.SnackBar(ft.Text(f"Error saving user: {str(ex)}")))
                    self.page.update()

        from utils import create_help_button
        dialog = ft.AlertDialog(
            title=ft.Text("Edit User" if user else "Add User"),
            content=ft.Column(
                [
                    ft.Row([username_field, create_help_button(self.page, "Username", User.help_text['username'])]),
                    ft.Row([password_field, create_help_button(self.page, "Password", User.help_text['password_hash'])]),
                    ft.Text(help_text, size=12, color=ft.Colors.GREY),
                    ft.Row([is_admin_checkbox, create_help_button(self.page, "Is Admin", User.help_text['is_admin'])]),
                ],
                tight=True,
                width=400
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.page.close(dialog)),
                ft.ElevatedButton("Save", on_click=save_user),
            ],
        )

        self.page.open(dialog)

