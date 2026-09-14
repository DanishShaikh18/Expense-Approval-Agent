import sqlite3
import csv
from datetime import datetime
from database import DB_PATH, HISTORY_CSV_PATH
from models import State

def budget_check_node(state: State) -> dict:
    """
    Budget check (deterministic code).
    Outputs budget_status: within_budget or over_budget.
    """
    receipt_data = state.get("receipt_data")
    if not receipt_data:
        return {"budget_status": "within_budget"}

    employee_id = state.get("employee_id")
    new_amount = receipt_data.total_amount
    new_date = receipt_data.date
    
    try:
        new_d = datetime.strptime(new_date, "%Y-%m-%d")
        period = new_d.strftime("%Y-%m")
    except ValueError:
        return {"budget_status": "within_budget"}
        
    # 1. Lookup department
    department = "Sales" # default
    with open(HISTORY_CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['employee_id'] == employee_id:
                department = row.get('department', 'Sales')
                break
                
    category = "meals" # Defaults for this demo

    # 2. Check budget cap
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT cap_amount FROM budgets WHERE department = ? AND category = ? AND period = ?", (department, category, period))
    row = c.fetchone()
    cap_amount = row[0] if row else 999999.0 # If no budget defined, assume unlimited
    
    # 3. Sum approved and processing amounts for this department/category/period
    # We join employee_history or just use the receipts_index which has employee_id, but receipts_index doesn't have department.
    # We need to sum by employee_id that belongs to that department.
    # For this demo, let's just assume we sum up all receipts in receipts_index for this employee_id's department.
    # To keep it simple, let's find all employee_ids in this department.
    dept_employees = set()
    with open(HISTORY_CSV_PATH, 'r', encoding='utf-8') as f:
        f.seek(0)
        reader = csv.DictReader(f)
        for r in reader:
            if r.get('department') == department:
                dept_employees.add(r['employee_id'])
                
    # Also add current employee just in case
    dept_employees.add(employee_id)
    
    placeholders = ",".join(["?"] * len(dept_employees))
    query = f"""
        SELECT SUM(amount) FROM receipts_index 
        WHERE employee_id IN ({placeholders}) 
        AND category = ? 
        AND strftime('%Y-%m', date) = ? 
        AND status IN ('approved', 'processing')
    """
    
    params = list(dept_employees) + [category, period]
    c.execute(query, params)
    sum_row = c.fetchone()
    total_spent = sum_row[0] if sum_row and sum_row[0] else 0.0
    
    conn.close()
    
    if total_spent > cap_amount:
        return {"budget_status": "over_budget"}
    else:
        return {"budget_status": "within_budget"}
