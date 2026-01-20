import sys
import os

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.append(src_dir)

print("Verifying imports...")

try:
    from views.project_view import ProjectView
    print("ProjectView imported successfully.")
    try:
        pv = ProjectView()
        print("ProjectView instantiated successfully.")
    except Exception as e:
        print(f"ProjectView instantiation FAILED: {e}")

    from views.change_log import ChangeLogView
    print("ChangeLogView imported successfully.")
    try:
        clv = ChangeLogView()
        print("ChangeLogView instantiated successfully.")
    except Exception as e:
        print(f"ChangeLogView instantiation FAILED: {e}")
    
    from views.dad_log import DADLogView
    print("DADLogView imported successfully.")
    try:
        dlv = DADLogView()
        print("DADLogView instantiated successfully.")
    except Exception as e:
        print(f"DADLogView instantiation FAILED: {e}")
    
    from views.project_plan import ProjectPlanView
    print("ProjectPlanView imported successfully.")
    try:
        ppv = ProjectPlanView()
        print("ProjectPlanView instantiated successfully.")
    except Exception as e:
        print(f"ProjectPlanView instantiation FAILED: {e}")
    
    from utils import create_responsive_dialog_content
    print("utils.create_responsive_dialog_content imported successfully.")

    print("\nAll views imported without syntax errors.")
    
except Exception as e:
    print(f"\nERROR: Verification failed with exception: {e}")
    sys.exit(1)
