
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import engine, Base, SessionLocal
from models import ChangeLog, ActionsLog, RiskLog, IssuesLog, DADLog, ProjectTask
from sqlalchemy import text, inspect

def migrate_dates():
    print("Starting Date Migration...")
    
    # 1. Inspect existing tables
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    session = SessionLocal()
    
    try:
        # 2. For each table, we need to ensure data format is valid YYYY-MM-DD
        # SQLite is loosely typed, so changing the model definition to Date doesn't strictly enforce it 
        # until we try to read it back as python object.
        # However, for correct behavior, we want to ensure all existing strings are parseable.
        
        # We will iterate through all relevant tables and try to parse dates.
        # If any are invalid, we will log them. Flet/SQLAlchemy Date type expects python date objects 
        # on write, and returns python date objects on read. 
        # But existing data is raw string "YYYY-MM-DD". SQLAlchemy's SQLite dialect usually handles 
        # reading this fine *if* the string is formatted correctly.
        
        models_with_dates = [
            (ChangeLog, ['date_received']),
            (ActionsLog, ['date_raised', 'target_end_date', 'actual_closure_date']),
            (RiskLog, ['date_raised']),
            (IssuesLog, ['date_raised', 'target_closure_date', 'actual_closure_date']),
            (DADLog, ['date_raised', 'date_agreed']),
            (ProjectTask, ['start_date', 'end_date'])
        ]
        
        for model, date_cols in models_with_dates:
            print(f"Checking {model.__tablename__}...")
            items = session.query(model).all()
            dirty = False
            
            for item in items:
                for col in date_cols:
                    val = getattr(item, col)
                    # It might be read as a string if SQLAlchemy hasn't fully realized it's a Date type yet 
                    # due to reflection or if it's just raw string in DB. 
                    # Actually, since we updated models.py, SQLAlchemy will try to convert it on access.
                    # If it fails, it might raise an error here.
                    
                    if isinstance(val, str) and val.strip():
                        try:
                            # Try to parse standard ISO format
                            parsed_date = datetime.strptime(val, "%Y-%m-%d").date()
                            # Write back the date object (SQLAlchemy will handle storage)
                            setattr(item, col, parsed_date)
                            dirty = True
                        except ValueError:
                            print(f"  [WARN] Invalid date format in {model.__tablename__} ID {item.id} Col {col}: {val}")
                            # Optional: Try other formats or set to None?
                            # For now, just warn.
                    
            if dirty:
                print(f"  Saving updates for {model.__tablename__}...")
                session.commit()
                
        print("Migration check complete. All valid string dates converted to Python Date objects where applicable.")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    migrate_dates()
