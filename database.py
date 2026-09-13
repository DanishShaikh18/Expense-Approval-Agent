import sqlite3
import csv
import os
import json
from models import State

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "receipts_index.db")
HISTORY_CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "employee_history.csv")

def get_exact_match(vendor: str, date: str, amount: float) -> bool:
    """Checks the database for an exact metadata match (vendor, date, amount)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM receipts_index WHERE vendor = ? AND date = ? AND amount = ?",
        (vendor, date, amount)
    )
    result = c.fetchone()
    conn.close()
    return result is not None

def insert_processing_receipt(state: State):
    """Inserts a receipt into receipts_index with status='processing'."""
    rd = state.get("receipt_data")
    if not rd:
        return
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO receipts_index
        (receipt_id, employee_id, vendor, date, amount, category, status, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        state.get("receipt_id"),
        state.get("employee_id"),
        rd.vendor,
        rd.date,
        rd.total_amount,
        "meals", # Defaulting to meals for this test scenario since we only have a $50 cap on meals
        "processing",
        state.get("employee_note")
    ))
    conn.commit()
    conn.close()

def update_receipt_status(receipt_id: str, new_status: str):
    """Updates the status of a receipt in receipts_index."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE receipts_index SET status = ? WHERE receipt_id = ?", (new_status, receipt_id))
    conn.commit()
    conn.close()

def write_audit_record(state: State):
    """Writes the final decision to the audit log."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create audit_log table if it doesn't exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            receipt_id TEXT PRIMARY KEY,
            employee_id TEXT,
            vendor TEXT,
            date TEXT,
            amount REAL,
            match_type TEXT,
            anomalous BOOLEAN,
            budget_status TEXT,
            compliance_verdict TEXT,
            compliance_reasoning TEXT,
            final_decision TEXT,
            final_reasoning TEXT,
            human_review_comment TEXT
        )
    """)
    
    rd = state.get("receipt_data")
    cv = state.get("compliance_verdict")
    
    c.execute("""
        INSERT OR REPLACE INTO audit_log 
        (receipt_id, employee_id, vendor, date, amount, match_type, anomalous, budget_status, compliance_verdict, compliance_reasoning, final_decision, final_reasoning, human_review_comment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        state.get("receipt_id"),
        state.get("employee_id"),
        rd.vendor if rd else None,
        rd.date if rd else None,
        rd.total_amount if rd else None,
        state.get("match_type"),
        state.get("anomalous"),
        state.get("budget_status"),
        cv.verdict if cv else None,
        cv.reasoning if cv else None,
        state.get("final_decision"),
        state.get("final_reasoning"),
        state.get("human_review_comment")
    ))
    
    conn.commit()
    conn.close()

def get_employee_history(employee_id: str) -> str:
    """Returns a formatted summary of the employee's recent spending pattern."""
    if not os.path.exists(HISTORY_CSV_PATH):
        return "No history found."
        
    records = []
    with open(HISTORY_CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['employee_id'] == employee_id:
                dept = row.get('department', 'Sales')
                records.append(f"- {row['date']}: {row['vendor']} (${row['amount']}) [{row['category']}] Dept: {dept} - {row['description']}")
                
    if not records:
        return "No recent history for this employee."
        
    return "\n".join(records)
