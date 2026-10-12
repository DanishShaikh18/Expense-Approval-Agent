import sqlite3
import os
import csv
from datetime import datetime
import difflib
from database import DB_PATH, HISTORY_CSV_PATH
from models import State

def pattern_check_node(state: State) -> dict:
    """
    Pattern check (deterministic code).
    Outputs match_type: exact_match, possible_match, no_match
    and anomalous: bool
    """
    claim_amount = state.get("claim_amount", 0.0)
    employee_id = state.get("employee_id")
    
    # Try to get vendor and date from receipt analysis for pattern matching if available
    receipt_analysis = state.get("receipt_analysis")
    new_vendor = ""
    if receipt_analysis and receipt_analysis.summary:
        # Just use summary for a naive similarity check if vendor isn't explicitly extracted anymore
        new_vendor = receipt_analysis.summary.strip().lower()
    
    new_date = datetime.now().strftime("%Y-%m-%d") # default to today for pattern check if no date
    
    match_type = "no_match"
    
    # 1. Duplicate Check
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT description, date, amount FROM receipts_index WHERE employee_id = ? AND receipt_id != ?", (employee_id, state.get("receipt_id")))
    past_receipts = c.fetchall()
    conn.close()

    try:
        new_d = datetime.strptime(new_date, "%Y-%m-%d")
    except ValueError:
        new_d = None

    for desc, d, a in past_receipts:
        v_norm = (desc or "").strip().lower()
        sim = difflib.SequenceMatcher(None, new_vendor, v_norm).ratio()
        
        # Exact match
        if sim > 0.85 and a == claim_amount and d == new_date:
            match_type = "exact_match"
            break
            
        # Possible match
        if match_type == "no_match" and sim > 0.85 and a == claim_amount and new_d:
            try:
                past_d = datetime.strptime(d, "%Y-%m-%d")
                if abs((new_d - past_d).days) <= 3:
                    match_type = "possible_match"
            except ValueError:
                pass
                
    # 2. Anomaly Check
    anomalous = False
    if new_d and os.path.exists(HISTORY_CSV_PATH):
        current_month = new_d.strftime("%Y-%m")
        monthly_totals = {}
        
        with open(HISTORY_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['employee_id'] == employee_id:
                    try:
                        r_date = datetime.strptime(row['date'], "%Y-%m-%d")
                        r_month = r_date.strftime("%Y-%m")
                        monthly_totals[r_month] = monthly_totals.get(r_month, 0.0) + float(row['amount'])
                    except ValueError:
                        continue
        
        # Exclude current month to get historical baseline
        historical_months = [m for m in monthly_totals.keys() if m != current_month]
        if historical_months:
            avg_monthly_spend = sum(monthly_totals[m] for m in historical_months) / len(historical_months)
            current_month_total = monthly_totals.get(current_month, 0.0) + claim_amount
            
            if avg_monthly_spend > 0 and current_month_total > (3 * avg_monthly_spend):
                anomalous = True

    return {
        "match_type": match_type,
        "anomalous": anomalous
    }
