import flet as ft
from sqlalchemy import Boolean, Text, Date
from datetime import datetime
from database import get_db_context
from models import Project
from utils import create_date_picker_field, create_help_button, set_required

class FormBuilder:
    def __init__(self, page, model_class, item=None, project_id_context=None, field_config=None):
        """
        page: Flet Page
        model_class: SQLAlchemy Model class
        item: Existing instance for Edit mode (None for Add mode)
        project_id_context: If provided, pre-selects/hides Project dropdown (e.g. inside a Project Plan)
        field_config: Dict of {col_name: config_dict} for custom behavior.
                      Supported keys: 'render' (callable), 'read_only' (bool), 'label' (str), 'help_text' (str)
        """
        self.page = page
        self.model_class = model_class
        self.item = item
        self.project_id_context = project_id_context
        self.field_config = field_config or {}
        self.controls = {} # Map column_name -> Flet Control

    def build_fields(self):
        fields = []
        # Exclude internal or auto-handled fields
        exclude = ['id', 'project', 'tasks', 'changes', 'actions', 'risks', 'issues', 'dads'] 
        
        # We iterate columns from the Table definition
        for col in self.model_class.__table__.columns:
            if col.name in exclude: continue

            # Special Handling for project_id
            if col.name == 'project_id':
                 control = self._build_project_selector()
                 fields.append(control)
                 self.controls['project_id'] = control
                 continue
            
            # Get Custom Config
            config = self.field_config.get(col.name, {})
            
            # --- 0. Custom Render Hook ---
            if 'render' in config:
                control = config['render'](col, self.item)
                self.controls[col.name] = control
                # Helper text override or from model
                help_text_override = config.get('help_text')
                if help_text_override:
                     fields.append(ft.Row([control, create_help_button(self.page, col.name, help_text_override)], vertical_alignment=ft.CrossAxisAlignment.CENTER))
                else: 
                     fields.append(self._wrap_with_help(control, col.name))
                continue

            # Check Overrides
            label = config.get('label', col.name.replace("_", " ").title())
            val = getattr(self.item, col.name) if self.item else None
            is_read_only = config.get('read_only', False)
            
            # --- 1. Enums / Dropdowns ---
            # Checks if model has corresponding options attribute (e.g., 'type' -> 'type_options')
            options_attr = f"{col.name}_options"
            if hasattr(self.model_class, options_attr):
                 options = getattr(self.model_class, options_attr)
                 control = ft.Dropdown(
                     label=label, 
                     value=val, 
                     options=[ft.dropdown.Option(o) for o in options],
                     expand=True,
                     disabled=is_read_only
                 )
            
            # --- 2. Booleans ---
            elif isinstance(col.type, Boolean):
                 control = ft.Checkbox(label=label, value=val if val is not None else False, disabled=is_read_only)
            
            # --- 3. Dates ---
            elif isinstance(col.type, Date):
                 # Convert python date object to YYYY-MM-DD string for display if needed
                 # utils.create_date_picker_field handles string input/output effectively
                 str_val = val.strftime('%Y-%m-%d') if val else None
                 
                 # Helper returns a Row [TextField, IconButton]
                 # We want to access the TextField to store in self.controls for getting value
                 # If read_only, we might just want a TextField?
                 if is_read_only:
                      control = ft.TextField(label=label, value=str_val or "", read_only=True, expand=True)
                      fields.append(self._wrap_with_help(control, col.name))
                      self.controls[col.name] = control
                      continue
                      
                 row = create_date_picker_field(self.page, label, initial_value=str_val)
                 
                 # Constraints logic (min/max date)? 
                 # Currently create_date_picker_field is simple.
                 # If config has 'min_date' etc, we might need a custom render or update create_date_picker_field.
                 # For now, let's assume complex date constraints use 'render' hook.
                 
                 # Store the TextField part in controls map for easy value retrieval
                 control = row.controls[0] 
                 # We use the whole row for display
                 fields.append(self._wrap_with_help(row, col.name))
                 self.controls[col.name] = control
                 continue # Skip standard append since we handled it
                 
            # --- 4. Text / Strings ---
            elif isinstance(col.type, Text):
                 control = ft.TextField(label=label, value=val if val else "", multiline=True, expand=True, read_only=is_read_only)
            else:
                 # Default String/Integer
                 control = ft.TextField(label=label, value=str(val) if val is not None else "", expand=True, read_only=is_read_only)

            # Apply Required Check
            if not col.nullable and not col.primary_key and not is_read_only:
                 set_required(control, True)

            self.controls[col.name] = control
            fields.append(self._wrap_with_help(control, col.name))
                
        return fields

    def _build_project_selector(self):
        """
        Builds the Project Dropdown.
        If project_id_context is set, it might be read-only or pre-selected.
        """
        # Load Projects
        with get_db_context() as db:
            projects = db.query(Project).all()
        
        options = [ft.dropdown.Option(key=str(p.id), text=p.name) for p in projects]
        
        # Determine Value
        val = None
        if self.item:
            val = str(self.item.project_id)
        elif self.project_id_context:
            val = str(self.project_id_context)
        else:
            # Fallback to session active project if available?
            # Or leave empty for user to select.
            session_proj = self.page.session.get("project_id")
            if session_proj:
                val = str(session_proj)

        dropdown = ft.Dropdown(
            label="Project",
            options=options,
            value=val,
            expand=True,
            disabled=bool(self.project_id_context) # Parse boolean if strictly enforced context
        )
        return set_required(dropdown, True)

    def _wrap_with_help(self, control, col_name):
        """
        Wraps a control (or row) with a Help Icon if help_text exists for `col_name` in the model.
        """
        help_text = getattr(self.model_class, 'help_text', {}).get(col_name)
        if help_text:
            # Check labels for standard controls to alignment
            label = getattr(control, 'label', col_name.title()) 
            
            # Avoid double nesting if control is already a Row (like DatePicker)
            # We assume if it's a Row, we can just append the help icon
            if isinstance(control, ft.Row):
                control.controls.append(create_help_button(self.page, label, help_text))
                return control

            return ft.Row(
                [control, create_help_button(self.page, label, help_text)], 
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5
            )
        return control

    def get_data(self):
        """
        Returns dict of {col_name: value} from controls.
        Format conversions (e.g. date string to date obj) happen here or in logic.
        Since we updated Models to Date type, SQLAlchemy expects python date objects.
        """
        data = {}
        for name, ctrl in self.controls.items():
            # Check for custom value getter logic
            config = self.field_config.get(name, {})
            if 'get_value' in config:
                val = config['get_value'](ctrl)
            else:
                val = ctrl.value
            
            # Handle empty strings for non-string types 
            # Allow SQLAlchemy to handle coercions or set None
            if val == "":
                val = None
            
            # Special Date Conversion because TextFields return strings
            # We need to map it back to date object if Model expects Date
            col = self.model_class.__table__.columns.get(name)
            if col is not None and isinstance(col.type, Date) and val:
                try:
                    if isinstance(val, str): # Verify it's a string before parsing
                         val = datetime.strptime(val, "%Y-%m-%d").date()
                except ValueError:
                    pass # Let validation fail elsewhere or keep as is

            data[name] = val
        return data
