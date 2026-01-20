
import flet as ft
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from views.project_plan import ProjectPlanView
from views.dad_log import DADLogView
from utils import create_responsive_dialog_content

def mock_page():
    p = ft.Page(None, None)
    p.session = {}
    return p

def verify_project_plan():
    print("Verifying ProjectPlanView...")
    try:
        view = ProjectPlanView(page=mock_page())
        # Simulate mount
        view.did_mount()
        print("ProjectPlanView loaded data successfully.")
        
        # Check if table has rows (might be empty if no data in DB, but at least no crash)
        rows_count = len(view.task_table.rows)
        print(f"ProjectPlanView table rows: {rows_count}")
        
    except Exception as e:
        print(f"FAIL: ProjectPlanView crashed: {e}")
        import traceback
        traceback.print_exc()

def verify_dad_log():
    print("Verifying DADLogView Dialog...")
    try:
        view = DADLogView(page=mock_page())
        view.did_mount()
        print("DADLogView loaded data successfully.")
        
        # Check open dialog (simulate add)
        # We can't easily Simulate UI interaction here without running app, 
        # but we can verify code structure didn't crash on import/init.
        
    except Exception as e:
        print(f"FAIL: DADLogView crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_project_plan()
    verify_dad_log()
