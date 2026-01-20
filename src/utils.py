import flet as ft
from datetime import datetime
from sqlalchemy.orm import Session
from database import get_db
from config import DateConfig

def create_date_picker_field(page, label, initial_value=None, on_change=None, read_only=True, expand=True):
    """
    Creates a standardized date picker field with calendar icon.
    Uses DateConfig for min/max dates.
    """
    field = ft.TextField(label=label, value=initial_value if initial_value else "", read_only=read_only, expand=expand)
    
    def on_date_change(e):
        if e.control.value:
            new_date = e.control.value.strftime('%Y-%m-%d')
            field.value = new_date
            field.update()
            if on_change:
                on_change(new_date)
    
    date_range = DateConfig.get_date_range()
    
    def pick_date(e):
        page.open(ft.DatePicker(
            first_date=date_range["first_date"],
            last_date=date_range["last_date"],
            on_change=on_date_change
        ))
        
    return ft.Row([
        field,
        ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=pick_date, tooltip=f"Pick {label}")
    ], spacing=5, expand=expand)

def set_required(control, required=True):
    """
    Appends an asterisk to the control's label if required.
    """
    if required and hasattr(control, "label") and control.label:
        if not control.label.endswith("*"):
            control.label = f"{control.label} *"
    return control

def show_help(page, title, message):
    """
    Shows a help message using a BottomSheet.
    This avoids closing any active AlertDialogs.
    """
    bs = ft.BottomSheet(
        ft.Container(
            ft.Column(
                [
                    ft.Text(title, size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(message),
                    ft.ElevatedButton("Close", on_click=lambda e: page.close(bs)),
                ],
                tight=True,
                spacing=20
            ),
            padding=20,
        ),
        open=True,
    )
    page.overlay.append(bs)
    page.update()

def create_help_button(page, title, message):
    """
    Creates a help icon button that shows a help dialog on click.
    """
    settings = get_settings(page)
    color = settings.get("heading_color", "blue")
    
    return ft.IconButton(
        ft.Icons.HELP_OUTLINE,
        icon_color=color,
        tooltip="Click for help",
        on_click=lambda e: show_help(page, title, message)
    )

def create_responsive_dialog_content(form_cols, notes_col):
    """
    Creates a responsive dialog layout using ResponsiveRow.
    Desktop: Form (Left 8) | Notes (Right 4)
    Mobile: Form (12) -> Stacked -> Notes (12)
    """
    # Use ResponsiveRow for main layout
    return ft.Container(
        content=ft.ResponsiveRow(
            [
                # Form Section
                ft.Column(
                    [form_cols],
                    col={"sm": 12, "md": 8},
                ),
                # Divider for visual separation (Vertical on Desktop, Horizontal implied on stack?)
                # VerticalDivider doesn't work well in ResponsiveRow flow.
                # We can just rely on spacing.
                
                # Notes Section
                ft.Column(
                    [notes_col], 
                    col={"sm": 12, "md": 4}
                )
            ],
            run_spacing=20, # Spacing between stacked items (Mobile)
            spacing=20 # Spacing between side-by-side items (Desktop)
        ),
        padding=10
    )

def create_quick_notes_column(page, notes_field, history_logic_callback, input_control=None):
    """
    Returns a Column containing the standard Quick Notes UI.
    notes_field: The TextField containing the history.
    history_logic_callback: Function(new_note_text, note_date) -> Updates DB and notes_field value.
    input_control: Optional existing TextField for input. If None, one is created.
    """
    # Use generic helper
    quick_note_date_row = create_date_picker_field(
        page, 
        "Date", 
        initial_value=datetime.now().strftime("%Y-%m-%d"),
        expand=False # Compact for this row
    )
    # The helper returns a Row [TextField, IconButton]. Access the field via controls[0]
    quick_note_date_field = quick_note_date_row.controls[0]
    quick_note_date_field.width = 150 # Set specific width for notes

    quick_note_text = input_control if input_control else ft.TextField(label="Quick Note", multiline=True, expand=True)
    
    def on_add_click(e):
        if not quick_note_text.value:
            return
        history_logic_callback(quick_note_text.value, quick_note_date_field.value)
        quick_note_text.value = ""
        quick_note_text.update()
        page.update()

    # Stacked Layout: Date on top, Text+Button below for full width
    quick_note_row = ft.Column(
        [
            ft.Container(quick_note_date_row, width=200),
            ft.Row(
                [
                    quick_note_text, 
                    ft.IconButton(ft.Icons.ADD_CIRCLE, on_click=on_add_click, tooltip="Add Note", icon_color=ft.Colors.GREEN, icon_size=30)
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
        ],
        spacing=10
    )

    return ft.Column(
        [
            # Header with Help
            ft.Row([
                ft.Text("Notes", weight=ft.FontWeight.BOLD, size=20),
                # Hardcoded help message for generic notes
                create_help_button(page, "Notes", "Add quick updates here. They are saved with a timestamp.")
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            
            ft.Text("Add Quick Note", weight=ft.FontWeight.BOLD),
            quick_note_row,
            ft.Divider(),
            ft.Text("History", weight=ft.FontWeight.BOLD),
            notes_field
        ],
        expand=1,
        scroll=ft.ScrollMode.AUTO,
    )

def create_quick_notes_dialog(page, item, model_class, load_data_callback):
    """
    Creates and opens a dialog for viewing and adding quick notes.
    """
    notes_field = ft.TextField(label="Notes History", value=item.notes if item else "", multiline=True, min_lines=5, read_only=True)
    # External input control to be accessed by 'Save' button in dialog actions
    input_field = ft.TextField(label="Quick Note", multiline=True, expand=True)
    
    def logic_callback(text, date_str):
        from database import get_db_context
        with get_db_context() as db:
            try:
                i = db.get(model_class, item.id)
                new_entry = f"[{date_str}] {text}\n"
                current_notes = i.notes if i.notes else ""
                i.notes = new_entry + ("\n" + current_notes if current_notes else "")
                db.commit()
                # Update UI Field
                notes_field.value = i.notes
                notes_field.update()
            except Exception as ex:
                db.rollback()
                page.open(ft.SnackBar(ft.Text(f"Error adding note: {str(ex)}")))

    content_col = create_quick_notes_column(page, notes_field, logic_callback, input_control=input_field)

    def on_save_click(e):
        if input_field.value:
            # Date defaults to today if we don't access the private picker field inside column. 
            # If they specifically typed in the box and hit save, use today's date.
            logic_callback(input_field.value, datetime.now().strftime("%Y-%m-%d"))
            input_field.value = ""
            input_field.update()
            page.close(dialog)
            page.open(ft.SnackBar(ft.Text("Note added successfully")))
            if load_data_callback:
                load_data_callback() # Refresh parent if needed
        else:
            page.close(dialog)

    def on_close_click(e):
        page.close(dialog)
        if load_data_callback:
            load_data_callback()

    dialog = ft.AlertDialog(
        title=ft.Text(f"Notes for Item #{item.id}"),
        content=ft.Container(
            content=content_col,
            width=600,
            height=400, # Constrain height for dialog
        ),
        actions=[
            ft.TextButton("Close", on_click=on_close_click),
            ft.ElevatedButton("Save Note", on_click=on_save_click),
        ],
    )
    page.open(dialog)

def create_filter_dialog(page, columns, apply_callback):
    """
    Creates and opens a dialog for filtering columns.
    columns: list of dicts {'label': 'Status', 'key': 'status', 'type': 'text'/'dropdown', 'options': []}
    """
    filter_controls = {}
    
    dialog_content = []
    
    for col in columns:
        if col['type'] == 'text':
            control = ft.TextField(label=col['label'], expand=True)
        elif col['type'] == 'dropdown':
            control = ft.Dropdown(label=col['label'], options=[ft.dropdown.Option(o) for o in col['options']], expand=True)
        
        filter_controls[col['key']] = control
        dialog_content.append(control)

    def apply_filters(e):
        filters = {k: v.value for k, v in filter_controls.items() if v.value}
        apply_callback(filters)
        page.close(dialog)

    def clear_filters(e):
        for control in filter_controls.values():
            control.value = None
            control.update()
        apply_callback({})
        # page.close(dialog) # Keep open or close? Let's keep open to see cleared state or close? User usually wants to see results.
        page.close(dialog)

    dialog = ft.AlertDialog(
        title=ft.Text("Filter Columns"),
        content=ft.Column(
            dialog_content,
            tight=True,
            width=400,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            ft.TextButton("Clear All", on_click=clear_filters),
            ft.TextButton("Cancel", on_click=lambda e: page.close(dialog)),
            ft.ElevatedButton("Apply", on_click=apply_filters),
        ],
    )
    page.open(dialog)

def get_settings(page):
    """
    Retrieves settings from client storage.
    Returns a dict with defaults if not found.
    """
    default_settings = {
        "theme_mode": "dark", # Default to Dark as requested
        "seed_color": "blue",
        "heading_color": "blue", # Default heading color
        "columns": {}
    }
    
    try:
        settings = page.client_storage.get("app_settings")
        if not settings:
            return default_settings
        
        # Merge with defaults to ensure all keys exist
        for key, value in default_settings.items():
            if key not in settings:
                settings[key] = value
        return settings
    except Exception:
        return default_settings

def save_settings(page, settings):
    """
    Saves settings to client storage.
    """
    try:
        page.client_storage.set("app_settings", settings)
    except Exception as e:
        print(f"Error saving settings: {e}")

def get_visible_columns(page, view_name, default_columns):
    """
    Returns a list of visible column names for a given view.
    default_columns: List of all available column names.
    """
    settings = get_settings(page)
    view_settings = settings.get("columns", {}).get(view_name, [])
    
    if not view_settings:
        return default_columns # Default to all visible
    
    return view_settings

def show_column_selector_dialog(page, view_name, all_columns, on_change):
    """
    Shows a dialog to select visible columns for a view.
    """
    settings = get_settings(page)
    current_visible = settings.get("columns", {}).get(view_name, all_columns)
    
    checkboxes = []
    for col in all_columns:
        checkboxes.append(ft.Checkbox(label=col, value=col in current_visible))
        
    def save_columns(e):
        new_visible = [cb.label for cb in checkboxes if cb.value]
        
        # Update settings
        settings = get_settings(page)
        if "columns" not in settings:
            settings["columns"] = {}
        settings["columns"][view_name] = new_visible
        save_settings(page, settings)
        
        page.close(dialog)
        on_change() # Callback to refresh view
        
    dialog = ft.AlertDialog(
        title=ft.Text(f"Select Columns for {view_name}"),
        content=ft.Column(
            checkboxes,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: page.close(dialog)),
            ft.ElevatedButton("Save", on_click=save_columns),
        ],
    )
    page.open(dialog)
