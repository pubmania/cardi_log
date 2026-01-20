import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy.orm import Session
from models import ProjectTask
from database import get_db
import io
from datetime import datetime, date

def ensure_datetime(val):
    """Helper to ensure value is a datetime object. Handles string and date objects."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    if isinstance(val, str):
        try:
            return datetime.strptime(val, "%Y-%m-%d")
        except ValueError:
            return None
    return None

def generate_template_dataframe():
    """Returns an empty DataFrame with the required columns for Project Tasks."""
    columns = ["Task ID", "Task Name", "Resource", "Workstream", "Start Date", "End Date", "Completion %"]
    return pd.DataFrame(columns=columns)

def export_tasks_to_file(project_id, file_format="csv"):
    """
    Exports tasks for a given project to a CSV or Excel file (in-memory bytes).
    """
    from database import get_db_context
    with get_db_context() as db:
        tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
        # Sort tasks by hierarchy to ensure consistent export order
        tasks.sort(key=lambda x: get_task_sort_key(x.task_id))
        
        data = []
        for t in tasks:
            data.append({
                "Task ID": t.task_id,
                "Task Name": t.task_name,
                "Resource": t.resource,
                "Workstream": t.workstream,
                "Start Date": t.start_date,
                "End Date": t.end_date,
                "Completion %": t.completion
            })
        
        df = pd.DataFrame(data, columns=["Task ID", "Task Name", "Resource", "Workstream", "Start Date", "End Date", "Completion %"])
        
        output = io.BytesIO()
        if file_format == "csv":
            df.to_csv(output, index=False)
        elif file_format == "xlsx":
            df.to_excel(output, index=False)
        
        output.seek(0)
        return output

import re

def generate_task_id(session, project_id):
    """
    Generates a unique Task ID for the given project.
    Finds the highest top-level ID (TASKX) and increments it.
    """
    # Get all task IDs for the project
    tasks = session.query(ProjectTask.task_id).filter(ProjectTask.project_id == project_id).all()
    existing_ids = [t[0] for t in tasks if t[0]]
    
    max_id = 0
    for tid in existing_ids:
        # Match TASK followed by digits, ignoring sub-tasks (e.g. TASK1.1) for max calculation
        # We only care about the top level number to determine the next one
        match = re.match(r"^TASK(\d+)", tid)
        if match:
            num = int(match.group(1))
            if num > max_id:
                max_id = num
    
    next_num = max_id + 1
    return f"TASK{next_num}"

def generate_subtask_id(session, project_id, parent_task_id):
    """
    Generates a unique Sub-Task ID.
    e.g. TASK1 -> TASK1.1, TASK1.1 -> TASK1.1.1
    """
    # Find all tasks that start with parent_task_id + "."
    # e.g. for TASK1, find TASK1.1, TASK1.2 (but not TASK1.1.1 yet, though regex handles it)
    pattern = f"^{re.escape(parent_task_id)}\\.(\\d+)$"
    
    tasks = session.query(ProjectTask.task_id).filter(
        ProjectTask.project_id == project_id,
        ProjectTask.task_id.like(f"{parent_task_id}.%")
    ).all()
    
    max_sub = 0
    for t in tasks:
        match = re.match(pattern, t[0])
        if match:
            num = int(match.group(1))
            if num > max_sub:
                max_sub = num
                
    next_sub = max_sub + 1
    return f"{parent_task_id}.{next_sub}"

def update_parent_completion(session, parent_task):
    """
    Recursively updates parent completion based on children.
    """
    if not parent_task:
        return

    children = parent_task.children
    
    if not children:
        return
        
    total_duration = 0
    weighted_sum = 0
    
    for c in children:
         comp = c.completion or 0
         # Calculate duration in days, default 1
         start = ensure_datetime(c.start_date) or datetime.now()
         end = ensure_datetime(c.end_date) or start
         duration = (end - start).days + 1
         if duration < 1: duration = 1 # Minimum 1 day weight
         
         total_duration += duration
         weighted_sum += (comp * duration)
    
    avg_comp = int(weighted_sum / total_duration) if total_duration > 0 else 0
    
    if parent_task.completion != avg_comp:
        parent_task.completion = avg_comp
        session.add(parent_task) # Mark for update
        # Recurse up
        if parent_task.parent:
            update_parent_completion(session, parent_task.parent)

def update_hierarchy_dates(session, task):
    """
    Ensures that if a child's dates expand beyond the parent, the parent is updated.
    This cascades up the tree.
    """
    if not task.parent:
        return

    parent = task.parent
    changed = False
    
    # Check Start Date (Parent should be <= Child)
    # If Child Start < Parent Start -> Parent Start = Child Start
    try:
        t_start = ensure_datetime(task.start_date)
        t_end = ensure_datetime(task.end_date)
        p_start = ensure_datetime(parent.start_date)
        p_end = ensure_datetime(parent.end_date)
        
        # User Logic: bidirectional cascading
        if t_end > p_end:
            parent.end_date = task.end_date
            changed = True
            
        if t_start < p_start:
            parent.start_date = task.start_date
            changed = True
            
        # Recursive check up
        if changed:
            session.add(parent)
            update_hierarchy_dates(session, parent)
            # Also update parent completion if duration changed
            # But update_hierarchy_dates is usually called during save which also triggers update_parent_completion separately.
            
    except Exception as e:
        print(f"Date parsing error in hierarchy update: {e}")


def import_tasks_from_file(project_id, file_content, filename):
    """
    Imports tasks from a CSV or Excel file content.
    Updates existing tasks by Task ID or creates new ones.
    """
    from database import get_db_context
    with get_db_context() as db:
        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(file_content))
            elif filename.endswith(".xlsx"):
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                return False, "Unsupported file format"

            # Data Cleaning
            # Handle Completion %: Remove '%' and convert to int, default to 0
            df["Completion %"] = df["Completion %"].astype(str).str.replace('%', '').replace('nan', '0').replace('', '0')
            df["Completion %"] = pd.to_numeric(df["Completion %"], errors='coerce').fillna(0).astype(int)

            # Handle Dates: Parse various formats to YYYY-MM-DD
            for date_col in ["Start Date", "End Date"]:
                df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
                df[date_col] = df[date_col].fillna("") # Handle invalid dates as empty string

            # Iterate and upsert
            added_count = 0
            updated_count = 0
            
            # Sort dataframe by Task ID so parents are processed before children
            df['sort_key'] = df['Task ID'].apply(lambda x: get_task_sort_key(str(x)) if pd.notna(x) else "")
            df = df.sort_values(by="sort_key")
            
            for _, row in df.iterrows():
                task_id = str(row["Task ID"]) if pd.notna(row["Task ID"]) and str(row["Task ID"]).strip() != "" else None
                
                # Resolve Parent ID Logic
                parent_id = None
                if task_id and "." in task_id:
                    # e.g. TASK1.1 -> Parent is TASK1
                    parent_id_str = task_id.rsplit(".", 1)[0]
                    # Look for parent in DB
                    p_obj = db.query(ProjectTask).filter(ProjectTask.project_id == project_id, ProjectTask.task_id == parent_id_str).first()
                    if p_obj: 
                        parent_id = p_obj.id

                if task_id:
                    # Update existing or create with specific ID
                    task = db.query(ProjectTask).filter(ProjectTask.project_id == project_id, ProjectTask.task_id == task_id).first()
                    if task:
                        task.task_name = row["Task Name"]
                        task.resource = row["Resource"] if pd.notna(row["Resource"]) else ""
                        task.workstream = row["Workstream"] if pd.notna(row["Workstream"]) else ""
                        task.start_date = row["Start Date"]
                        task.end_date = row["End Date"]
                        task.completion = row["Completion %"]
                        # If we found a parent from ID structure, update it. 
                        # Note: This allows fixing broken hierarchy via import if IDs match.
                        if parent_id: task.parent_id = parent_id
                        updated_count += 1
                    else:
                        new_task = ProjectTask(
                            project_id=project_id,
                            task_id=task_id,
                            task_name=row["Task Name"],
                            resource=row["Resource"] if pd.notna(row["Resource"]) else "",
                            workstream=row["Workstream"] if pd.notna(row["Workstream"]) else "",
                            start_date=row["Start Date"],
                            end_date=row["End Date"],
                            completion=row["Completion %"],
                            parent_id=parent_id
                        )
                        db.add(new_task)
                        db.flush() # Flush to allow immediate children to find this parent
                        added_count += 1
                else:
                    # Create new task with auto-generated ID
                    new_id = generate_task_id(db, project_id)
                    new_task = ProjectTask(
                        project_id=project_id,
                        task_id=new_id,
                        task_name=row["Task Name"],
                        resource=row["Resource"] if pd.notna(row["Resource"]) else "",
                        workstream=row["Workstream"] if pd.notna(row["Workstream"]) else "",
                        start_date=row["Start Date"],
                        end_date=row["End Date"],
                        completion=row["Completion %"]
                    )
                    db.add(new_task)
                    db.flush()
                    added_count += 1
            
            # Post-import: Ensure hierarchy consistency (dates/completion)
            if added_count > 0 or updated_count > 0:
                 # Get all tasks again to perform updates
                 all_tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
                 for t in all_tasks:
                     if t.parent_id:
                         update_hierarchy_dates(db, t)
                         # completion update is bottom-up, so we might need multiple passes or careful ordering
                         # update_parent_completion is recursive, so calling on leaves is sufficient.
                 
                 # Second pass for completion from leaves up?
                 # Or just iterate all and update parents.
                 for t in all_tasks:
                      if t.children:
                          update_parent_completion(db, t)

            db.commit()
            return True, f"Imported {added_count} new tasks, updated {updated_count} existing tasks."
        except Exception as e:
            db.rollback()
            return False, str(e)

import numpy as np
import seaborn as sns
import datetime as dt

import re

def get_task_sort_key(task_id):
    """
    Generates a sortable key from a Task ID.
    Splits text and numbers, and pads numbers with zeros.
    Example: TASK1.1 -> TASK00001.00001
    """
    if not task_id:
        return ""
    
    # Split by numbers
    parts = re.split(r'(\d+)', str(task_id))
    padded_parts = []
    
    for part in parts:
        if part.isdigit():
            # Pad numbers to 5 digits (enough for 99999 tasks/subtasks)
            padded_parts.append(part.zfill(5))
        else:
            padded_parts.append(part)
            
    return "".join(padded_parts)

import plotly.utils
import json
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import seaborn as sns
import datetime as dt

def _plot_gantt(df, title, height=None, theme_mode="dark"):
    """
    Helper function to plot Gantt chart from a DataFrame.
    Returns a Plotly Figure object.
    theme_mode: "dark" or "light"
    """
    # ... existing data prep ...
    # Project level variables
    p_Start = df['Start'].min()
    p_End = df['End'].max()
    if pd.isna(p_Start) or pd.isna(p_End):
            return None
            
    p_duration = (p_End - p_Start).days + 1

    # Add relative date
    df['rel_Start'] = (df['Start'] - p_Start).dt.days

    # Add work completion
    df['w_comp'] = round(df['Completion'] * df['duration'] / 100, 2)

    # Colouring based on Workstream (or Project Name for portfolio)
    color_col = 'Workstream' if 'Workstream' in df.columns else 'Task Label'
    
    unique_items = df[color_col].unique()
    num_items = len(unique_items)
    # Use seaborn to generate colors, convert to hex for Plotly
    palette = sns.color_palette("bright", num_items)
    colors = palette.as_hex()
    c_dict = dict(zip(unique_items, colors))

    # Sorting by Task Order (using the created column)
    if 'Task Order' in df.columns:
        df = df.sort_values(by=['Task Order'], ascending=True).reset_index(drop=True)
    else:
        df = df.sort_values(by=['Start'], ascending=True).reset_index(drop=True)

    # --- Plotting Logic ---
    
    dia_df = df[df['duration'] == 0]

    # Main timeline (rectangles)
    rect = px.timeline(
        df, 
        x_start="Start", 
        x_end="End", 
        y="Task Label", 
        color=color_col, 
        text="Task Label",
        hover_name="Task Label", 
        hover_data=["Start", "End", "Completion"],
        color_discrete_map=c_dict
    )
    
    rect.update_traces(textposition='outside')
    rect.update_yaxes(autorange='reversed')
    
    # Dynamic styling based on theme
    is_dark = theme_mode == "dark"
    template = "plotly_dark" if is_dark else "plotly_white"
    text_color = "white" if is_dark else "black"
    grid_color = "#444" if is_dark else "#eee"
    selector_bg = "#333" if is_dark else "#f0f0f0"
    selector_active = "#555" if is_dark else "#ccc"

    chart_height = height if height else max(800, len(df) * 50) # Increased min height and row height
    
    # Update Layout for Dark Theme and Responsiveness
    rect.update_layout(
        title=title, 
        showlegend=True, 
        height=chart_height,
        autosize=True, # Ensure it fills container
        template=template,
        plot_bgcolor='rgba(0,0,0,0)', # Transparent background
        paper_bgcolor='rgba(0,0,0,0)', # Transparent background
        font=dict(color=text_color), # Dynamic text color
        hovermode="closest",
        dragmode="pan", # Default to panning
        bargap=0.5,
        bargroupgap=0.1,
        xaxis_range=[df.Start.min() - dt.timedelta(days=5), df.End.max() + dt.timedelta(days=5)],
        xaxis=dict(
            showgrid=True,
            gridcolor=grid_color,
            rangeslider_visible=True,
            side="top",
            tickmode='auto',
            ticks="outside",
            tickson="boundaries",
            tickwidth=.1,
            layer='below traces',
            ticklen=20,
            tickfont=dict(family='Arial', size=12, color=text_color),
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(step="all")
                ]),
                bgcolor=selector_bg,
                activecolor=selector_active,
                x=0,
                y=-0.1
            ),
            type="date"
        ),
        yaxis=dict(
            title="Activities",
            autorange="reversed",
            automargin=True,
            showgrid=True,
            gridcolor=grid_color,
            showticklabels=True,
            tickfont=dict(family='Arial', size=12, color=text_color)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.1,
            title="",
            xanchor="right",
            x=1
        )
    )

    # Milestones (diamonds/stars)
    dia = None
    if not dia_df.empty:
        dia = px.scatter(
            dia_df, 
            x="Start", 
            y="Task Label", 
            color=color_col, 
            symbol_sequence=['star'],
            hover_name="Task Label", 
            hover_data=["Start"],
            color_discrete_map=c_dict
        )
        dia.update_traces(marker=dict(size=10, line=dict(width=1)))
        dia.update_yaxes(autorange="reversed")

    # Combine traces
    data_traces = rect.data
    if dia:
        data_traces += dia.data
        
    fig = go.Figure(data=data_traces, layout=rect.layout)
    return fig



def generate_gantt_chart_from_tasks(tasks, title="Project Schedule", theme_mode="dark"):
    """
    Generates a Plotly Gantt chart from a list of ProjectTask objects.
    """
    import pandas as pd
    import numpy as np
    
    if not tasks:
        return None

    data = []
    for t in tasks:
        # Support both object and dict access
        if isinstance(t, dict):
            start = t.get('start_date')
            end = t.get('end_date')
            t_id = str(t.get('task_id', ''))
            t_name = str(t.get('task_name', 'Unnamed Task'))
            t_resource = str(t.get('resource', 'Unassigned'))
            t_completion = str(t.get('completion', '0%'))
            t_workstream = str(t.get('workstream', 'General'))
        else:
            # SQLAlchemy Object
            start = getattr(t, 'start_date', None)
            end = getattr(t, 'end_date', None)
            t_id = str(getattr(t, 'task_id', ''))
            t_name = str(getattr(t, 'task_name', 'Unnamed Task'))
            t_resource = str(getattr(t, 'resource', 'Unassigned'))
            t_completion = str(getattr(t, 'completion', '0%'))
            t_workstream = str(getattr(t, 'workstream', 'General'))

        if not start or not end:
            continue
            
        data.append({
            "Task ID": t_id,
            "Task": t_name,
            "Start": start,
            "End": end,
            "Resource": t_resource,
            "Completion": t_completion,
            "Workstream": t_workstream
        })
    
    if not data:
        return None

    df = pd.DataFrame(data)
    
    # Create Task Order column
    from utils_data import get_task_sort_key
    df['Task Order'] = df['Task ID'].apply(get_task_sort_key)
    
    # Level column
    df['Level'] = np.where(df['Task ID'].str.contains(r'\.', regex=True), 'Sub', 'Top')

    # Combine Task ID and Task
    df['Task Label'] = df['Task ID'] + ' - ' + df['Task']

    # Clean Completion
    try:
        df['Completion'] = df['Completion'].astype(str).str.rstrip('.!? %')
        df['Completion'] = pd.to_numeric(df['Completion'], errors='coerce').fillna(0).astype(int)
    except Exception as e:
        print(f"Error processing completion: {e}")
        df['Completion'] = 0

    # Convert dates
    for col in ['Start', 'End']:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # Add Duration
    df['duration'] = (df['End'] - df['Start']).dt.days
    
    return _plot_gantt(df, title, theme_mode=theme_mode)

def generate_gantt_chart(project_id, theme_mode="dark"):
    """
    Generates a Plotly Gantt chart for the given project using advanced customization.
    Returns a Plotly Figure object.
    """
    from database import get_db_context
    with get_db_context() as db:
        try:
            tasks = db.query(ProjectTask).filter(ProjectTask.project_id == project_id).all()
            return generate_gantt_chart_from_tasks(tasks, "Project Schedule", theme_mode)
        except Exception as e:
            print(f"Error generating Gantt chart: {e}")
            import traceback
            traceback.print_exc()
            return None

def generate_portfolio_gantt_chart(projects_data, theme_mode="dark"):
    """
    Generates a Portfolio Gantt chart where each bar is a project.
    projects_data: List of dicts with 'name', 'start_date', 'end_date', 'status'
    Returns a Plotly Figure object.
    """
    try:
        if not projects_data:
            return None

        data = []
        for p in projects_data:
            if not p['start_date'] or not p['end_date']:
                continue
            data.append({
                "Task Label": p['name'], # Treat Project Name as Task Label
                "Workstream": p['status'], # Color by Status
                "Start": p['start_date'],
                "End": p['end_date'],
                "Completion": 0 # Default for now
            })
        
        if not data:
            return None

        df = pd.DataFrame(data)
        
        # Convert dates
        for col in ['Start', 'End']:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            
        # Add Duration
        df['duration'] = (df['End'] - df['Start']).dt.days
        
        return _plot_gantt(df, "Portfolio Schedule", theme_mode=theme_mode)

    except Exception as e:
        print(f"Error generating Portfolio Gantt chart: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_gantt_html(project_id=None, projects_data=None, is_portfolio=False, tasks=None, title="Detailed Schedule"):
    """
    Generates a Plotly Gantt chart HTML file.
    Args:
        project_id: For single project Gantt
        projects_data: For portfolio Gantt
        is_portfolio: Boolean flag
        tasks: Optional list of tasks to render directly (bypassing DB query)
        title: Title for the chart
    Returns the absolute path to the file.
    """
    import os
    # Force dark theme for HTML export as requested
    if tasks:
         fig = generate_gantt_chart_from_tasks(tasks, title, theme_mode="dark")
         filename = f"gantt_export_{title.replace(' ', '_')}.html"
    elif is_portfolio:
        fig = generate_portfolio_gantt_chart(projects_data, theme_mode="dark")
        filename = "gantt_portfolio.html"
    else:
        fig = generate_gantt_chart(project_id, theme_mode="dark")
        filename = f"gantt_project_{project_id}.html"

    if not fig:
        return None
    
    # Ensure background is opaque dark for external browser viewing
    # This overrides the transparent background used in the app
    fig.update_layout(
        paper_bgcolor='#1a1a1a', # Dark grey background
        plot_bgcolor='#1a1a1a'
    )
    
    try:
        filepath = os.path.abspath(filename)
        fig.write_html(filepath)
        return filepath
    except Exception as e:
        print(f"Error saving Gantt HTML: {e}")
        return None
        
def get_time_scale_config(view_mode="Days"):
    """
    Returns configuration for the time scale view.
    """
    import datetime as dt
    from dateutil.relativedelta import relativedelta

    config = {
        "Days": {
            "step": relativedelta(days=1),
            "format": "%d\n%b", # 01 Jan
            "slot_width": 30, # Base width for 1 day
            "label": "Daily"
        },
        "Weeks": {
            "step": relativedelta(weeks=1),
            "format": "W%W\n%b", # W01 Jan
            "slot_width": 40, # Base width for 1 week
            "label": "Weekly"
        },
        "Months": {
            "step": relativedelta(months=1),
            "format": "%b\n%Y", # Jan 2024
            "slot_width": 50, # Base width for 1 month
            "label": "Monthly"
        },
        "Quarters": {
            "step": relativedelta(months=3),
            "format": "%Y", # Q1 2024 - handled manually
            "slot_width": 60, # Base width for 1 quarter
            "label": "Quarterly"
        },
        "Years": {
            "step": relativedelta(years=1),
            "format": "%Y", # 2024
            "slot_width": 80, # Base width for 1 year
            "label": "Yearly"
        }
    }
    return config.get(view_mode, config["Days"])

def get_x_offset_for_date(date_obj, min_date, view_mode, slot_width):
    """
    Calculates the X pixel offset for a given date based on the view mode.
    """
    import datetime as dt
    
    if not date_obj or not min_date:
        return 0

    if view_mode == "Days":
        return (date_obj - min_date).days * slot_width
    
    elif view_mode == "Weeks":
        # Days diff / 7 * slot_width
        return (date_obj - min_date).days / 7 * slot_width
        
    elif view_mode == "Months":
        # Year diff * 12 + Month diff + (Day / DaysInMonth)
        # Simplified: Just average days 30.44
        # More precise:
        year_diff = date_obj.year - min_date.year
        month_diff = date_obj.month - min_date.month
        
        # Calculate fraction of current month
        # next_month_start = date_obj.replace(day=1) + relativedelta(months=1)
        # days_in_month = (next_month_start - date_obj.replace(day=1)).days
        # But for simplicity and speed, using 30.44 days per month approximation for converting days is easier
        # Or just strictly calendar months:
        
        total_months = year_diff * 12 + month_diff
        
        # Add day fraction
        # day_fraction = (date_obj.day - 1) / 30.44 
        day_fraction = (date_obj.day - 1) / 31.0 # Using 31 max to keep safely within
        
        return (total_months + day_fraction) * slot_width
    
    elif view_mode == "Quarters":
        # Similar to months but / 3
        year_diff = date_obj.year - min_date.year
        month_diff = date_obj.month - min_date.month
        total_months = year_diff * 12 + month_diff
        
        day_fraction = (date_obj.day - 1) / 31.0
        total_quarters = (total_months + day_fraction) / 3.0
        
        return total_quarters * slot_width

    elif view_mode == "Years":
        year_diff = date_obj.year - min_date.year
        day_of_year = date_obj.timetuple().tm_yday
        fraction = (day_of_year - 1) / 365.25 # Approx
        
        return (year_diff + fraction) * slot_width

    return 0

def generate_native_gantt_chart(tasks, expand_chart=True, view_mode="Days"):
    """
    Generates a Native Flet Gantt chart using Stack and Containers.
    Returns a Flet Control (Column).
    view_mode: "Days", "Weeks", "Months", "Quarters", "Years"
    """
    import flet as ft
    from datetime import datetime
    
    if not tasks:
         return ft.Column(
            [ft.Icon(ft.Icons.ASSIGNMENT_LATE, size=50), ft.Text("No tasks found.")], 
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

    # 1. Pre-process Data
    data = []
    min_date = None
    max_date = None
    
    for t in tasks:
        if not t.start_date or not t.end_date:
            continue
        try:
            start = ensure_datetime(t.start_date)
            end = ensure_datetime(t.end_date)
            
            if min_date is None or start < min_date: min_date = start
            if max_date is None or end > max_date: max_date = end
            
            data.append({
                "id": t.task_id,
                "name": t.task_name,
                "start": start,
                "end": end,
                "duration": (end - start).days + 1,
                "completion": t.completion if t.completion is not None else 0,
                "workstream": t.workstream
            })

        except Exception as e:
            print(f"Skipping task {t.task_id}: {e}")
            continue
            
    if not data:
         return ft.Text("No valid task dates found.")
         
    # Sort Data by smart sort key
    data.sort(key=lambda x: get_task_sort_key(x['id']))
         
    # Add buffer to dates
    min_date = min_date - dt.timedelta(days=2)
    max_date = max_date + dt.timedelta(days=5)
    total_days = (max_date - min_date).days + 1
    
    # 2. Config
    scale_config = get_time_scale_config(view_mode)
    slot_width = scale_config["slot_width"]
    step = scale_config["step"]
    fmt = scale_config["format"]
    
    # Calculate Total Width
    total_slots = get_x_offset_for_date(max_date, min_date, view_mode, 1.0) # Raw slots count
    chart_width = int(total_slots * slot_width) + slot_width # +1 buffer

    row_height = 40
    header_height = 50
    label_width = 200
    
    # 3. Build Header (Dates)
    date_cells = []
    current = min_date
    while current <= max_date:
        # Format label
        label_text = current.strftime(fmt)
        if view_mode == "Weeks":
            # week number fix
            label_text = f"W{current.isocalendar()[1]}\n{current.strftime('%b')}"
        elif view_mode == "Quarters":
             q = (current.month - 1) // 3 + 1
             label_text = f"Q{q}\n{current.strftime('%Y')}"
            
        date_cells.append(
            ft.Container(
                content=ft.Text(label_text, size=10, text_align=ft.TextAlign.CENTER),
                width=slot_width,
                height=header_height,
                border=ft.border.only(right=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
                alignment=ft.alignment.center
            )
        )
        current += step
        
    header_row = ft.Row(
        [
            ft.Container(width=label_width, content=ft.Text("Task", weight=ft.FontWeight.BOLD), padding=10),
            ft.Row(date_cells, spacing=0)
        ],
        spacing=0
    )
    
    # 4. Build Rows/Bars
    rows = []
    import random
    
    # Simple color map
    unique_ws = list(set([d['workstream'] for d in data]))
    colors = [ft.Colors.BLUE, ft.Colors.GREEN, ft.Colors.ORANGE, ft.Colors.PURPLE, ft.Colors.RED, ft.Colors.TEAL]
    color_map = {ws: colors[i % len(colors)] for i, ws in enumerate(unique_ws)}
    
    for item in data:
        # Calculate bar position
        start_offset = get_x_offset_for_date(item['start'], min_date, view_mode, slot_width)
        end_offset = get_x_offset_for_date(item['end'], min_date, view_mode, slot_width)
        
        # Ensure at least minimal width
        bar_width = max(5, end_offset - start_offset)
        # If showing single day in large scales (e.g. Years), ensure visibility
        if bar_width < 5: bar_width = 5
        
        # Color
        color = color_map.get(item['workstream'], ft.Colors.BLUE)
        
        # Bar Container
        bar = ft.Container(
            width=bar_width,
            height=20,
            bgcolor=color,
            border_radius=5,
            tooltip=f"{item['name']}\nStart: {item['start'].strftime('%Y-%m-%d')}\nEnd: {item['end'].strftime('%Y-%m-%d')}\n{item['completion']}%",
            on_hover=lambda e: e.control.update(), # Simple interactive trigger
        )
        
        # Row Stack (Grid Line + Bar)
        # We use a Stack to place the bar at absolute X position relative to the timeline start
        grid_lines = ft.Container(
            width=chart_width,
            height=row_height,
            gradient=ft.LinearGradient(
                begin=ft.alignment.center_left,
                end=ft.alignment.center_right,
                colors=[ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE), ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE)],
                stops=[0.5, 0.5],
                tile_mode=ft.GradientTileMode.REPEATED # Simulated grid lines might be heavy, stick to simple border
            ),
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
        )
        
        # Since Stack doesn't support easy horizontal scroll with fixed headers in a simple way without independent scrolls,
        # We will put the Bar inside a Container with margin-left.
        
        timeline_content = ft.Stack(
            [
                ft.Container(
                    width=chart_width, 
                    height=row_height,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)))
                ), # Grid background line
                ft.Container(content=bar, margin=ft.margin.only(left=start_offset, top=10))
            ],
            width=chart_width,
            height=row_height
        )

        row = ft.Row(
            [
                ft.Container(
                    width=label_width, 
                    content=ft.Text(item['name'], no_wrap=True, tooltip=item['name']), 
                    padding=ft.padding.only(left=10),
                    alignment=ft.alignment.center_left,
                    height=row_height,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)))
                ),
                timeline_content
            ],
            spacing=0
        )
        rows.append(row)

    # 5. Assemble
    # We need a scrollable row for the timeline part.
    # To keep headers and rows aligned, we put them in a column, but the timeline part needs to move together.
    # Simplest native gantt:
    # Scale: Header Row + List of Rows.
    # Split into Left (Fixed Labels) and Right (Scrollable Timeline).
    
    # Left Column (Task Names)
    left_col_rows = [
        ft.Container(height=header_height, content=ft.Text("Task", weight=ft.FontWeight.BOLD), padding=10, alignment=ft.alignment.center_left)
    ]
    for item in data:
        # Calculate indentation
        indent_level = str(item['id']).count('.') if item['id'] else 0
        indent_padding = 10 + (indent_level * 20)
        
        left_col_rows.append(
            ft.Container(
                height=row_height, 
                content=ft.Text(item['name'], size=12, no_wrap=True, tooltip=item['name']), 
                padding=ft.padding.only(left=indent_padding),
                alignment=ft.alignment.center_left,
                border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)))
            )
        )
        
    left_col = ft.Column(left_col_rows, spacing=0, width=label_width)
    
    # Right Column (Timeline)
    # Header
    timeline_header = ft.Row(date_cells, spacing=0, height=header_height)
    
    # Legend
    legend_items = []
    for ws, color in color_map.items():
         legend_items.append(
             ft.Row([
                 ft.Container(width=12, height=12, bgcolor=color, border_radius=2),
                 ft.Text(ws if ws else "General", size=10)
             ], spacing=5)
         )
    
    # Bottom Legend Row
    legend_row = ft.Row(legend_items, wrap=False,  scroll=ft.ScrollMode.AUTO, spacing=15)
    
    # Bars
    timeline_rows = []
    for item in data:
        start_offset = get_x_offset_for_date(item['start'], min_date, view_mode, slot_width)
        end_offset = get_x_offset_for_date(item['end'], min_date, view_mode, slot_width)
        
        # Ensure at least minimal width
        bar_width = max(5, end_offset - start_offset)
        # If showing single day in large scales (e.g. Years), ensure visibility
        if bar_width < 5: bar_width = 5

        color = color_map.get(item['workstream'], ft.Colors.BLUE)
        
        timeline_rows.append(
             ft.Container(
                width=chart_width, # Full width to allow consistent scrolling
                height=row_height,
                border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
                content=ft.Stack(
                    [
                        # Vertical grid lines (simulated or simplified)
                        ft.Container(
                            content=ft.Container(
                                width=bar_width,
                                height=20,
                                bgcolor=color,
                                border_radius=5,
                                tooltip=f"{item['name']} ({item['completion']}%)",
                            ),
                            margin=ft.margin.only(left=start_offset, top=10)
                        )
                    ]
                )
             )
        )
        
    right_col_content = ft.Column([timeline_header] + timeline_rows, spacing=0, width=chart_width)
    right_area = ft.Row([right_col_content], scroll=ft.ScrollMode.AUTO, expand=True)
    
    return ft.Column([
        ft.Text("Legend", size=12, weight=ft.FontWeight.BOLD),
        legend_row,
        ft.Divider(),
        ft.Row([
            left_col,
            right_area
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START)
    ], scroll=ft.ScrollMode.AUTO if not expand_chart else None)
    
    # Main Layout
    return ft.Row(
        [
            left_col,
            ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
            right_area
        ],
        expand=expand_chart,
        spacing=0,
        height=min(800, max(500, len(rows) * row_height + header_height + 50))
    )

def generate_native_portfolio_gantt_chart(projects, expand_chart=True, on_click_project=None, view_mode="Days"):
    """
    Generates a Native Flet Portfolio Gantt chart.
    projects: List of Project objects or dicts with name, start_date, end_date
    on_click_project: Callback function(project_id)
    view_mode: "Days", "Weeks", "Months", "Quarters", "Years"
    """
    import flet as ft
    from datetime import datetime
    
    if not projects:
         return ft.Column(
            [ft.Icon(ft.Icons.ASSIGNMENT_LATE, size=50), ft.Text("No projects found.")], 
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

    # 1. Pre-process Data
    data = []
    min_date = None
    max_date = None
    
    for p in projects:
        # Depending on if it's an object or dict
        p_name = getattr(p, 'name', p.get('name')) if hasattr(p, 'name') or isinstance(p, dict) else "Unknown"
        p_id = getattr(p, 'id', p.get('id', None)) if hasattr(p, 'id') or isinstance(p, dict) else None

        # Start/End date might need to be calculated if not direct properties
        # But for portfolio view we usually pass pre-calculated data or existing properties
        # Assuming input is list of dicts from project_plan.py query logic
        
        start_str = p.get('start_date') if isinstance(p, dict) else getattr(p, 'start_date', None)
        end_str = p.get('end_date') if isinstance(p, dict) else getattr(p, 'end_date', None)
        status = p.get('status') if isinstance(p, dict) else getattr(p, 'status', 'Active')

        if not start_str or not end_str:
            continue
            
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d") if isinstance(start_str, str) else start_str
            end = datetime.strptime(end_str, "%Y-%m-%d") if isinstance(end_str, str) else end_str
            
            if min_date is None or start < min_date: min_date = start
            if max_date is None or end > max_date: max_date = end
            
            data.append({
                "id": p_id,
                "name": p_name,
                "start": start,
                "end": end,
                "duration": (end - start).days + 1,
                "status": status
            })
        except Exception as e:
            print(f"Skipping project {p_name}: {e}")
            continue
            
    if not data:
         return ft.Text("No valid project dates found.")
         
    # Add buffer
    min_date = min_date - dt.timedelta(days=5)
    max_date = max_date + dt.timedelta(days=5)
    total_days = (max_date - min_date).days + 1
    
    # 2. Config
    scale_config = get_time_scale_config(view_mode)
    slot_width = scale_config["slot_width"]
    step = scale_config["step"]
    fmt = scale_config["format"]
    
    # Calculate Total Width
    total_slots = get_x_offset_for_date(max_date, min_date, view_mode, 1.0)
    chart_width = int(total_slots * slot_width) + slot_width

    row_height = 40
    header_height = 50
    label_width = 200
    
    # 3. Header
    date_cells = []
    current = min_date
    while current <= max_date:
        # Format label
        label_text = current.strftime(fmt)
        if view_mode == "Weeks":
            label_text = f"W{current.isocalendar()[1]}\n{current.strftime('%b')}"
        elif view_mode == "Quarters":
             q = (current.month - 1) // 3 + 1
             label_text = f"Q{q}\n{current.strftime('%Y')}"

        date_cells.append(
            ft.Container(
                content=ft.Text(label_text, size=10, text_align=ft.TextAlign.CENTER),
                width=slot_width,
                height=header_height,
                border=ft.border.only(right=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
                alignment=ft.alignment.center
            )
        )
        current += step
        
    # 4. Rows
    rows = []
    import random
    
    # Color map for statuses
    status_colors = {
        "Active": ft.Colors.GREEN,
        "Completed": ft.Colors.BLUE,
        "On Hold": ft.Colors.ORANGE,
        "Cancelled": ft.Colors.RED,
        "Proposed": ft.Colors.PURPLE
    }
    
    for item in data:
        start_offset = get_x_offset_for_date(item['start'], min_date, view_mode, slot_width)
        end_offset = get_x_offset_for_date(item['end'], min_date, view_mode, slot_width)
        bar_width = max(5, end_offset - start_offset)
        color = status_colors.get(item['status'], ft.Colors.GREY)
        
        # GestureDetector for double tap
        bar_content = ft.Container(
            width=bar_width,
            height=20,
            bgcolor=color,
            border_radius=5,
            tooltip=f"{item['name']}\n{item['status']}\n{item['start'].strftime('%Y-%m-%d')} - {item['end'].strftime('%Y-%m-%d')}",
            on_hover=lambda e: e.control.update(),
        )
        
        bar_control = bar_content

        timeline_content = ft.Stack(
            [
                ft.Container(
                    width=chart_width, 
                    height=row_height,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)))
                ),
                ft.Container(content=bar_control, margin=ft.margin.only(left=start_offset, top=10))
            ],
            width=chart_width,
            height=row_height
        )
        
        # Make the label clickable too
        label_content = ft.Container(
                    width=label_width, 
                    content=ft.Text(item['name'], no_wrap=True, weight=ft.FontWeight.BOLD), 
                    padding=ft.padding.only(left=10),
                    alignment=ft.alignment.center_left,
                    height=row_height,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)))
                )
        label_control = label_content

        row = ft.Row(
            [
                label_control,
                timeline_content
            ],
            spacing=0
        )
        rows.append(row)
        
    left_col = ft.Column([ft.Container(height=header_height, width=label_width, content=ft.Text("Project", weight=ft.FontWeight.BOLD), padding=10)], spacing=0)
    
    # Since rows combine label + timeline, we can just stack them below the header row
    # Header Row: [Label_Header, Timeline_Header]
    
    header_row = ft.Row(
        [
            ft.Container(height=header_height, width=label_width, content=ft.Text("Project", weight=ft.FontWeight.BOLD), padding=10),
            ft.Row([ft.Row(date_cells, spacing=0)], scroll=ft.ScrollMode.AUTO, expand=True) # Header scroll sync is hard without advanced controls
        ],
        spacing=0
    )
    # reuse the logic from main gantt: Left Col + Right Col(scrollable)
    
    # Re-structure for split view
    left_rows = [ft.Container(height=header_height, width=label_width, content=ft.Text("Project", weight=ft.FontWeight.BOLD), padding=10, alignment=ft.alignment.center_left)]
    right_rows = [ft.Row(date_cells, spacing=0, height=header_height)]
    
    for item in data:
        # Label
        label = ft.Text(item['name'], no_wrap=True, weight=ft.FontWeight.BOLD)
        l_cont = ft.Container(
            height=row_height, width=label_width, padding=ft.padding.only(left=10), 
            alignment=ft.alignment.center_left, 
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
            content=label
        )
        # if on_click_project and item['id']:
        #      l_cont = ft.GestureDetector(content=l_cont, on_double_tap=lambda e, pid=item['id']: on_click_project(pid))
        left_rows.append(l_cont)
        
        # Timeline
        start_offset = get_x_offset_for_date(item['start'], min_date, view_mode, slot_width)
        end_offset = get_x_offset_for_date(item['end'], min_date, view_mode, slot_width)
        bar_width = max(5, end_offset - start_offset)
        color = status_colors.get(item['status'], ft.Colors.GREY)
        
        b_cont = ft.Container(
            width=bar_width, height=20, bgcolor=color, border_radius=5,
            tooltip=f"{item['name']}\n{item['status']}\n{item['start'].strftime('%Y-%m-%d')} - {item['end'].strftime('%Y-%m-%d')}"
        )
        # if on_click_project and item['id']:
        #      b_cont = ft.GestureDetector(content=b_cont, on_double_tap=lambda e, pid=item['id']: on_click_project(pid))
             
        t_row = ft.Stack(
            [
                ft.Container(width=chart_width, height=row_height, border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)))),
                ft.Container(content=b_cont, margin=ft.margin.only(left=start_offset, top=10))
            ],
            width=chart_width, height=row_height
        )
        right_rows.append(t_row)
        
    left_col = ft.Column(left_rows, spacing=0)
    right_col = ft.Column(right_rows, spacing=0, width=chart_width)
    right_scroll = ft.Row([right_col], scroll=ft.ScrollMode.AUTO, expand=True)
    
    return ft.Column([
        ft.Row([left_col, right_scroll], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START)
    ], scroll=ft.ScrollMode.AUTO if not expand_chart else None)
        
    # 5. Assemble
    left_col_rows = [
        ft.Container(height=header_height, content=ft.Text("Project", weight=ft.FontWeight.BOLD), padding=10, alignment=ft.alignment.center_left)
    ]
    for item in data:
        left_col_rows.append(
            ft.Container(
                height=row_height, 
                content=ft.Text(item['name'], size=12, no_wrap=True), 
                padding=ft.padding.only(left=10),
                alignment=ft.alignment.center_left,
                border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)))
            )
        )
    
    left_col = ft.Column(left_col_rows, spacing=0, width=label_width)
    
    timeline_header = ft.Row(date_cells, spacing=0, height=header_height)
    
    timeline_rows = []
    for item in data:
         start_offset = (item['start'] - min_date).days * day_width
         bar_width = item['duration'] * day_width
         color = status_colors.get(item['status'], ft.Colors.GREY)
         
         timeline_rows.append(
             ft.Container(
                width=chart_width,
                height=row_height,
                border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))),
                content=ft.Stack(
                    [
                        ft.Container(
                            content=ft.Container(
                                width=bar_width,
                                height=20,
                                bgcolor=color,
                                border_radius=5,
                                tooltip=f"{item['name']}",
                            ),
                            margin=ft.margin.only(left=start_offset, top=10)
                        )
                    ]
                )
             )
         )
         
    right_col_content = ft.Column([timeline_header] + timeline_rows, spacing=0, width=chart_width)
    right_area = ft.Row([right_col_content], scroll=ft.ScrollMode.AUTO, expand=True)

    return ft.Row(
        [
            left_col,
            ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
            right_area
        ],
        expand=expand_chart,
        spacing=0,
        height=min(800, max(500, len(rows) * row_height + header_height + 50))
    )
