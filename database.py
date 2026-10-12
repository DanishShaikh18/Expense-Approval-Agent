import sqlite3
import os
from datetime import datetime
from models import State, ReceiptAnalysis

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "receipts_index.db")
HISTORY_CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "employee_history.csv")

def insert_processing_receipt(state: State, analysis: ReceiptAnalysis):
    """Inserts a receipt into receipts_index with status='processing'.
    Uses the employee's claim_amount as the authoritative amount to encumber budget.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # We use today's date since we don't force date collection from the employee,
    # or we could parse from analysis if available. Defaulting to today.
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # We store the claim_amount as the authoritative amount
    c.execute("""
        INSERT OR REPLACE INTO receipts_index
        (receipt_id, employee_id, vendor, date, amount, category, status, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        state.get("receipt_id"),
        state.get("employee_id"),
        analysis.summary[:50] if analysis and analysis.summary else "Unknown Vendor",
        date_str,
        state.get("claim_amount", 0.0),
        state.get("expense_category", "meals"),
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
            claim_amount REAL,
            expense_category TEXT,
            receipt_amount REAL,
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
    
    ra = state.get("receipt_analysis")
    cv = state.get("compliance_verdict")
    
    c.execute("""
        INSERT OR REPLACE INTO audit_log 
        (receipt_id, employee_id, claim_amount, expense_category, receipt_amount, match_type, anomalous, budget_status, compliance_verdict, compliance_reasoning, final_decision, final_reasoning, human_review_comment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        state.get("receipt_id"),
        state.get("employee_id"),
        state.get("claim_amount", 0.0),
        state.get("expense_category"),
        ra.receipt_amount if ra else None,
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
