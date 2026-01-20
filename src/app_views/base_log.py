import flet as ft
from database import get_db_context
from models import Project
from config import AppConfig
from utils import (
    get_settings, 
    save_settings, 
    create_filter_dialog, 
    show_column_selector_dialog, 
    create_date_picker_field,
    create_responsive_dialog_content,
    create_quick_notes_column
)
from utils_forms import FormBuilder
from .base_page import BasePageView

class BaseLogView(BasePageView):
    def __init__(self, page, model_class, title, columns_config, icon=ft.Icons.LIST, enable_project_filter=True):
        super().__init__(page, title, icon, enable_project_filter)
        self.model_class = model_class
        # Columns Config: List of tuples (key, label, cell_func)
        self.columns_config = columns_config
        
        self.data_table = ft.DataTable(
            columns=[],
            rows=[],
            # heading_row_color removed
            data_row_min_height=40,
            column_spacing=20,
            data_row_max_height=float("inf"), # Allow wrapping
        )
        
        # BasePageView sets self.content. We can rely on it or override controls.
        # But we need to load data specific to this log.
        self.load_data() 

    def handle_resize(self, e):
        self.load_data()

    # on_project_change, load_projects managed by BasePageView

    # --- Shared Helpers ---
    def get_rag_color(self, rag):
        if rag == "Red": return ft.Colors.RED
        elif rag == "Amber": return ft.Colors.AMBER
        elif rag == "Green": return ft.Colors.GREEN
        return ft.Colors.GREY

    def get_rag_cell(self, item):
        rag = getattr(item, 'rag', "")
        return ft.DataCell(
            ft.Container(
                width=20, height=20, border_radius=10, 
                bgcolor=self.get_rag_color(rag), 
                tooltip=rag
            )
        )

    # load_projects managed by BasePageView

    def load_data(self):
        print(f"DEBUG: Loading data for {self.title}")
        try:
            # Determine screen size (Mobile vs Desktop)
            is_mobile = self.page.width < 768

            with get_db_context() as db:
                query = db.query(self.model_class)
                
                # Filter by Project
                if self.enable_project_filter and self.project_dropdown and self.project_dropdown.value and self.project_dropdown.value != "all":
                    if hasattr(self.model_class, 'project_id'):
                        query = query.filter(self.model_class.project_id == int(self.project_dropdown.value))
                
                # Apply other filters
                if hasattr(self, 'filters') and self.filters:
                    for key, value in self.filters.items():
                        if hasattr(self.model_class, key):
                            col_attr = getattr(self.model_class, key)
                            # Basic string contains or exact match
                            # Check if value is in dropdown options (Exact)
                            is_dropdown = key in ['status', 'rag', 'type', 'probability', 'impact']
                            if is_dropdown:
                                query = query.filter(col_attr == value)
                            else:
                                query = query.filter(col_attr.ilike(f"%{value}%"))
                
                items = query.all()
                print(f"DEBUG: Found {len(items)} items for {self.title}")

                if is_mobile:
                    self.render_mobile_view(items)
                else:
                    self.render_desktop_view(items)
        
            self.page.update()
        except Exception as e:
            print(f"ERROR in load_data for {self.title}: {e}")
            import traceback
            traceback.print_exc()
            self.content.controls = [ft.Text(f"Error loading data: {e}", color=ft.Colors.RED)]
            self.page.update()

    def render_desktop_view(self, items):
        try:
            # 1. Determine Visible Columns
            all_col_keys = [c[0] for c in self.columns_config]
            visible_keys = get_settings(self.page).get("columns", {}).get(self.model_class.__tablename__, all_col_keys)
            
            visible_config = [c for c in self.columns_config if c[0] in visible_keys]
            
            # Use the pre-configured DataColumn objects directly
            self.data_table.columns = [c[1] for c in visible_config]
            
            # Add Actions Column
            self.data_table.columns.append(ft.DataColumn(ft.Text("Actions", weight="bold")))

            self.data_table.rows = []
            for item in items:
                cells = [c[2](item) for c in visible_config]
                
                # Action Buttons
                actions_list = []
                if hasattr(self.model_class, 'notes'):
                    actions_list.append(
                        ft.IconButton(ft.Icons.NOTE_ADD, icon_color=ft.Colors.GREEN, tooltip="Notes",
                                      on_click=lambda e, i=item: self.show_notes_dialog(e, i))
                    )
                
                actions_list.extend([
                        ft.IconButton(ft.Icons.EDIT, icon_color=ft.Colors.BLUE, tooltip="Edit",
                                      on_click=lambda e, i=item: self.show_dialog(i)),
                        ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED, tooltip="Delete",
                                      on_click=lambda e, i=item: self.delete_item(i)),
                ])

                action_cell = ft.DataCell(
                    ft.Row(actions_list, spacing=0)
                )
                cells.append(action_cell)
                self.data_table.rows.append(ft.DataRow(cells=cells))

            heading_color = get_settings(self.page).get("heading_color", ft.Colors.BLUE)
            self.title_text.color = heading_color
        
        # Determine Mobile vs Desktop
        # ...
        
            # Determine Mobile vs Desktop
            # ...
            
            # Header Rendering using BasePageView
            extra_actions = [
                 ft.IconButton(ft.Icons.VIEW_COLUMN, on_click=self.open_column_selector, tooltip="Select Columns"),
                 ft.IconButton(ft.Icons.FILTER_LIST, on_click=self.open_filter_dialog, tooltip="Filter"),
                 ft.IconButton(ft.Icons.ADD, on_click=lambda e: self.show_dialog(), tooltip="Add Item"),
            ]
            
            self.content.controls = [
                self.render_header(extra_actions=extra_actions),
                ft.Divider(),
                ft.Column(
                    [
                        ft.Row(
                            [self.data_table],
                            scroll=ft.ScrollMode.ALWAYS,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        )
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True
                )
            ]
        except Exception as e:
            print(f"ERROR in render_desktop_view: {e}")
            import traceback
            traceback.print_exc()
            self.content.controls.append(ft.Text(f"Error rendering view: {e}", color=ft.Colors.RED))
            
    def show_notes_dialog(self, e, item):
        from utils import create_quick_notes_dialog
        create_quick_notes_dialog(self.page, item, self.model_class, self.load_data)

    def open_filter_dialog(self, e):
        columns = []
        for key, col_def, _ in self.columns_config:
            # Skip Actions and potentially ID if not needed (ID is okay to filter though)
            if key.lower() == "actions":
                continue
            
            # Determine Label
            label = key.title()
            if isinstance(col_def, ft.DataColumn) and isinstance(col_def.label, ft.Text):
                label = col_def.label.value
            
            # Determine Type and Options
            col_type = 'text'
            options = []
            
            # 1. Check for specific *_options attribute in model
            # e.g. status -> status_options, type -> type_options
            options_attr = f"{key.lower()}_options"
            if hasattr(self.model_class, options_attr):
                options = getattr(self.model_class, options_attr)
                col_type = 'dropdown'
            
            # 2. Check for known standard dropdowns if not found per-model
            elif key.lower() == 'rag':
                options = ["Red", "Amber", "Green"]
                col_type = 'dropdown'
            elif key.lower() in ['priority', 'impact', 'probability']:
                 # Fallback if model doesn't define them, though RiskLog/IssueLog usually do or are simple text
                 # Let's keep it text if not explicitly defined in model to avoid assumptions?
                 # Actually standardizing these is good.
                 options = ["High", "Medium", "Low"]
                 col_type = 'dropdown'
            
            # 3. Special handling for booleans? (ChangeLog impacts?)
            # ChangeLog impacts are seperate columns in DB but combined in View?
            # View column is "Impacts", key might be "impacts"?
            # If key not in model, filtering might fail in load_data unless we handle it.
            # BaseLogView load_data does: getattr(self.model_class, key).
            # So if columns_config has a key that isn't a model attribute, filter will crash load_data.
            # We should check if model has the attribute.
            # Use lowercase check because keys are typically Title Case in config but snake_case in model
            attr_name = key.lower()
            if key == "ID": attr_name = "id" # Explicit mapping for ID if needed, though lower covers it
            
            if not hasattr(self.model_class, attr_name) and not hasattr(self.model_class, attr_name + "_id"): # Allow foreign keys?
                # Special case: ChangeLog "impacts" which is a computed column in View
                # We can't easily filter on it via generic query.
                continue

            columns.append({
                'label': label,
                'key': attr_name, # Use the model attribute name for filtering
                'type': col_type,
                'options': options
            })

        create_filter_dialog(self.page, columns, self.apply_filters)

    def apply_filters(self, filters):
        # Store filters in session or instance? Instance.
        # self.filters needed.
        self.filters = filters
        self.load_data()

    def render_mobile_view(self, items):
        # Simplified Mobile Card View
        cards = []
        for item in items:
            # Default: Show ID, Title/Description, Status
            title = getattr(item, 'title', getattr(item, 'description', f'Item {item.id}'))
            status = getattr(item, 'status', 'N/A')
            
            rag_color = ft.Colors.TRANSPARENT
            if hasattr(item, 'rag'):
                rag = getattr(item, 'rag', "")
                if rag == "Red": rag_color = ft.Colors.RED
                elif rag == "Amber": rag_color = ft.Colors.AMBER
                elif rag == "Green": rag_color = ft.Colors.GREEN

            status_color = ft.Colors.GREY
            if status in ["Open", "Approved", "Active"]: status_color = ft.Colors.GREEN
            elif status in ["Closed", "Raised"]: status_color = ft.Colors.BLUE
            elif status == "On-Hold": status_color = ft.Colors.AMBER
            elif status in ["Cancelled", "Rejected"]: status_color = ft.Colors.RED

            status_content = ft.Container(
                 content=ft.Text(status, size=12, color=status_color),
                 padding=5,
                 border=ft.border.all(1, status_color),
                 border_radius=5
            )

            card_content = ft.Row([
                ft.Column([
                    ft.Text(title, weight="bold", size=16, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        status_content,
                        ft.Text(f"#{item.id}", size=12, color=ft.Colors.GREY)
                    ], alignment=ft.MainAxisAlignment.START, spacing=10)
                ], expand=True),
            ])

            # Add RAG indicator if applicable
            if hasattr(item, 'rag'):
                card_content.controls.append(
                    ft.Container(width=15, height=15, border_radius=15, bgcolor=rag_color, tooltip=getattr(item, 'rag',""))
                )
            
            # Add Quick Note Action (Prominent)
            if hasattr(self.model_class, 'notes'):
                card_content.controls.append(
                    ft.IconButton(ft.Icons.NOTE_ADD, icon_color=ft.Colors.GREEN, 
                                on_click=lambda e, i=item: self.show_notes_dialog(e, i))
                )

            # Add Actions Menu
            card_content.controls.append(
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT,
                    items=[
                        ft.PopupMenuItem(text="Edit", icon=ft.Icons.EDIT, on_click=lambda e, i=item: self.show_dialog(i)),
                        ft.PopupMenuItem(text="Delete", icon=ft.Icons.DELETE, on_click=lambda e, i=item: self.delete_item(i)),
                    ]
                )
            )

            card = ft.Card(
                content=ft.Container(
                    content=card_content,
                    padding=10,
                    on_click=lambda e, i=item: self.show_dialog(i), # Tap to View/Edit
                    ink=True, # Visual feedback
                )
            )
            cards.append(card)

        # Use BasePageView Header
        extra_actions = [
            ft.IconButton(ft.Icons.FILTER_LIST, on_click=self.open_filter_dialog, tooltip="Filter"),
            ft.IconButton(ft.Icons.ADD, on_click=lambda e: self.show_dialog(), tooltip="Add Item")
        ]

        self.content.controls = [
            self.render_header(extra_actions=extra_actions),
            ft.ListView(controls=cards, expand=True, spacing=10)
        ]

    def show_dialog(self, item=None):
        fb = FormBuilder(self.page, self.model_class, item)
        fields = fb.build_fields()

        # Split Fields and Notes
        form_controls = []
        notes_control_obj = None
        notes_key = 'notes'

        # FormBuilder returns a list of controls (some wrapped in Rows for Help text)
        # We need to find the one corresponding to 'notes'
        if notes_key in fb.controls:
            print(f"DEBUG: Found notes key in fb.controls. Value: '{fb.controls[notes_key].value}'")
            notes_control_obj = fb.controls[notes_key]
            
            # Filter fields list to exclude the notes control (and its wrapper row if any)
            # This is tricky because build_fields returns new objects (wrappers)
            # Strategy: Iterate built fields and check if they contain our notes control
            for field in fields:
                is_notes = False
                if field == notes_control_obj:
                    is_notes = True
                elif isinstance(field, ft.Row) and notes_control_obj in field.controls:
                    is_notes = True
                
                if not is_notes:
                    form_controls.append(field)
        else:
            print("DEBUG: notes key NOT FOUND in fb.controls")
            form_controls = fields

        # --- Notes Column (Right Side) ---
        notes_col = None
        if notes_control_obj:
            # We want to replace the standard TextField with our Quick Notes Column
            # Fix Layout Props: FormBuilder sets expand=True which breaks in scrollable column
            notes_control_obj.expand = False
            notes_control_obj.min_lines = 8
            # notes_control_obj.read_only = True # History should be read-only <-- REMOVED to allow editing
            
            # But we must keep the same TextField object so fb.get_data() works!
            # The Quick Notes Column wrapper takes a TextField and adds logic.
            
            def notes_logic(text, date_str):
                new_entry = f"[{date_str}] {text}\n"
                current = notes_control_obj.value if notes_control_obj.value else ""
                notes_control_obj.value = new_entry + ("\n" + current if current else "")
                notes_control_obj.update()

            # Ensure it's treated as multiline/min_lines for display
            notes_control_obj.multiline = True
            notes_control_obj.min_lines = 5
            
            notes_col = create_quick_notes_column(self.page, notes_control_obj, notes_logic)
        
        # --- Form Column (Left Side) ---
        # Create ResponsiveRow for form controls
        def form_wrapper(control):
             # Default to 6 cols (2 per row) on md, 12 on sm
             # But full width checks?
             # Heuristic: Description/Title usually full width? FormBuilder doesn't tell us.
             # Let's default to md=6, but if it's a huge text field maybe 12?
             return ft.Column([control], col={"sm": 12, "md": 6})

        form_items_layout = []
        for c in form_controls:
            # Check if it looks like a full-width field (e.g. description)
            # Access underlying control if wrapped
            underlying = c
            if isinstance(c, ft.Row) and len(c.controls) > 0:
                underlying = c.controls[0]
            
            is_large = False
            if isinstance(underlying, ft.TextField) and underlying.multiline:
                is_large = True
            
            form_items_layout.append(ft.Column([c], col={"sm": 12, "md": 12 if is_large else 6}))

        form_content = ft.ResponsiveRow(
            form_items_layout,
            run_spacing=10,
            spacing=10
        )
        
        # --- Combine Layout ---
        if notes_col:
            # Wrap in scrollable column like DADLogView
            content_container = create_responsive_dialog_content(form_content, notes_col)
            dialog_content = ft.Column([content_container], scroll=ft.ScrollMode.AUTO, expand=True)
        else:
            dialog_content = ft.Column([form_content], scroll=ft.ScrollMode.AUTO, expand=True)

        def on_save(e):
            data = fb.get_data()
            
            # Client-side Validation for Required Fields
            has_error = False
            for col in self.model_class.__table__.columns:
                if not col.nullable and not col.primary_key and col.name in fb.controls:
                    val = data.get(col.name)
                    # Use generic check for empty values
                    if not val or str(val).strip() == "":
                        control = fb.controls[col.name]
                        if hasattr(control, 'error_text'):
                            control.error_text = f"{col.name.title().replace('_', ' ')} is required"
                            control.update()
                        has_error = True
            
            if has_error:
                self.page.open(ft.SnackBar(ft.Text("Please fill in all required fields.")))
                self.page.update()
                return

            try:
                self.save_to_db(item, data)
                self.load_data()
                self.page.close(dialog)
                self.page.open(ft.SnackBar(ft.Text("Saved successfully!")))
                self.page.update()
            except Exception as ex:
                self.page.open(ft.SnackBar(ft.Text(f"Error: {str(ex)}")))
                self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"{'Edit' if item else 'Add'} {self.title}"),
            content=ft.Container(content=dialog_content, width=1200, height=800),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.page.close(dialog)),
                ft.ElevatedButton("Save", on_click=on_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True
        )
        self.page.open(dialog)

    def save_to_db(self, item, data):
        """
        Saves data to database. Can be overridden for custom logic (e.g. RAG calculation).
        """
        with get_db_context() as db:
            if item:
                # Update
                db_item = db.get(self.model_class, item.id)
                for k, v in data.items():
                    setattr(db_item, k, v)
            else:
                # Create
                new_item = self.model_class(**data)
                db.add(new_item)
            db.commit()

    def delete_item(self, item):
        def confirm_delete(e):
            with get_db_context() as db:
                db_item = db.get(self.model_class, item.id)
                if db_item:
                    db.delete(db_item)
                    db.commit()
            self.load_data()
            self.page.close(dlg)
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text("Are you sure you want to delete this item?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.page.close(dlg)),
                ft.TextButton("Delete", on_click=confirm_delete, style=ft.ButtonStyle(color=ft.Colors.RED)),
            ]
        )
        self.page.open(dlg)

    def open_column_selector(self, e):
        all_cols = [c[0] for c in self.columns_config]
        show_column_selector_dialog(self.page, self.model_class.__tablename__, all_cols, lambda: self.load_data())

