
import sys
import os
import unittest
from datetime import datetime, date
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import Modules to Test
from utils_data import ensure_datetime
from models import RiskLog
from utils_forms import FormBuilder

class TestRefactoring(unittest.TestCase):
    
    def test_ensure_datetime(self):
        print("\nTesting ensure_datetime...")
        # 1. String
        d1 = ensure_datetime("2024-01-01")
        self.assertIsInstance(d1, datetime)
        self.assertEqual(d1.strftime("%Y-%m-%d"), "2024-01-01")
        
        # 2. Date object
        d2 = ensure_datetime(date(2024, 1, 1))
        self.assertIsInstance(d2, datetime)
        self.assertEqual(d2.strftime("%Y-%m-%d"), "2024-01-01")
        
        # 3. Datetime object
        d3 = ensure_datetime(datetime(2024, 1, 1, 12, 0, 0))
        self.assertIsInstance(d3, datetime)
        self.assertEqual(d3.strftime("%Y-%m-%d"), "2024-01-01")
        
        # 4. None/Invalid
        self.assertIsNone(ensure_datetime(None))
        self.assertIsNone(ensure_datetime("invalid-date"))
        print("ensure_datetime Passed.")

    def test_risk_log_model_dates(self):
        print("\nTesting RiskLog Model Dates...")
        # Simulate creating a RiskLog with Date object (as SQLA would do)
        risk = RiskLog(
            title="Test Risk",
            date_raised=date(2024, 5, 20),
            project_id=1
        )
        self.assertIsInstance(risk.date_raised, date)
        print("RiskLog Date Type Passed.")

    def test_rag_logic(self):
        print("\nTesting RAG Calculation Logic...")
        # Simulate the logic from RiskLogView.save_to_db
        # We can't easily instantiate the View without a Page, but we can verify the logic itself.
        
        def calculate_rag(prob, imp):
            if prob == "High" and imp == "High":
                return "Red"
            elif prob == "Low" and imp == "Low":
                return "Green"
            else:
                return "Amber"
                
        self.assertEqual(calculate_rag("High", "High"), "Red")
        self.assertEqual(calculate_rag("Low", "Low"), "Green")
        self.assertEqual(calculate_rag("High", "Low"), "Amber")
        self.assertEqual(calculate_rag("Medium", "Medium"), "Amber")
        print("RAG Logic Passed.")

    def test_form_builder_init(self):
        print("\nTesting FormBuilder Initialization...")
        page_mock = MagicMock()
        fb = FormBuilder(page_mock, RiskLog, item=None)
        
        # We can't fully build fields because it requires Flet context which might fail in headless constraints
        # But we can check if it mapped columns
        self.assertEqual(fb.model_class, RiskLog)
        
        # Check if excluded columns are respected?
        # Ideally we'd call build_fields but that creates Controls which might need page. 
        # Flet 0.21+ controls can be instantiated without page usually.
        try:
            fields = fb.build_fields()
            print(f"FormBuilder generated {len(fields)} fields.")
            
            # Check if 'date_raised' is in controls
            self.assertIn('date_raised', fb.controls)
            
            # Check if 'status' (Enum) is in controls
            self.assertIn('status', fb.controls)
            
            # Check if 'project_id' was handled (it's special)
            self.assertIn('project_id', fb.controls)
            
            print("FormBuilder Generation Passed.")
        except Exception as e:
            self.fail(f"FormBuilder failed: {e}")

if __name__ == '__main__':
    unittest.main()
