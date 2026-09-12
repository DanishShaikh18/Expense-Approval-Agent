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
            duplicate_match TEXT,
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
        (receipt_id, employee_id, vendor, date, amount, duplicate_match, compliance_verdict, compliance_reasoning, final_decision, final_reasoning, human_review_comment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        state.get("receipt_id"),
        state.get("employee_id"),
        rd.vendor if rd else None,
        rd.date if rd else None,
        rd.total_amount if rd else None,
        state.get("duplicate_match"),
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
                records.append(f"- {row['date']}: {row['vendor']} (${row['amount']}) [{row['category']}] - {row['description']}")
                
    if not records:
        return "No recent history for this employee."
        
    return "\n".join(records)
