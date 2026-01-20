import sys
import os
from datetime import date

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import get_db_context
from models import DADLog, Project

def seed_dad_data():
    with get_db_context() as db:
        # Get a project
        project = db.query(Project).first()
        if not project:
            print("No projects found. Creating 'Sample Project'...")
            project = Project(name="Sample Project", start_date=date.today(), end_date=date.today())
            db.add(project)
            db.commit()
            db.refresh(project)

        print(f"Seeding DAD Log for Project: {project.name} (ID: {project.id})")

        entries = [
            DADLog(
                project_id=project.id,
                type="Decision",
                description="Selected Flet as the UI framework due to its Python-first approach and cross-platform capabilities.",
                status="Approved",
                date_raised=date(2025, 1, 15),
                raised_by="Architect",
                impact="High",
                notes="Critical architecture decision."
            ),
            DADLog(
                project_id=project.id,
                type="Assumption",
                description="Assuming the client will provide API access by Q2.",
                status="Raised",
                date_raised=date(2025, 2, 1),
                raised_by="Project Manager",
                impact="Medium",
                notes="Need to verify with IT team."
            ),
            DADLog(
                project_id=project.id,
                type="Dependency",
                description="Waiting for Security Audit completion before Go-Live.",
                status="Active",
                date_raised=date(2025, 3, 10),
                raised_by="Dev Lead",
                impact="High",
                notes="Audit scheduled for next week."
            ),
             DADLog(
                project_id=project.id,
                type="Decision",
                description="Use SQLite for local deployment simplification.",
                status="Approved",
                date_raised=date(2025, 1, 20),
                raised_by="Lead Dev",
                impact="Low",
            ),
        ]

        for entry in entries:
             db.add(entry)
        
        db.commit()
        print(f"Successfully added {len(entries)} DAD Log entries.")

if __name__ == "__main__":
    seed_dad_data()
