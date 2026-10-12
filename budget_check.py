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
    claim_amount = state.get("claim_amount", 0.0)
    employee_id = state.get("employee_id")
    category = state.get("expense_category", "meals").lower()
    
    # We don't have a strict date for the claim itself from the employee in the state,
    # so we can use today's date, or try to extract from receipt if present.
    # Since this is a prototype, let's just use the current month for budget checking.
    period = datetime.now().strftime("%Y-%m")
        
    # 1. Lookup department
    department = "Sales" # default
    with open(HISTORY_CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['employee_id'] == employee_id:
                department = row.get('department', 'Sales')
                break

    # 2. Check budget cap
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT cap_amount FROM budgets WHERE department = ? AND category = ? AND period = ?", (department, category, period))
    row = c.fetchone()
    cap_amount = row[0] if row else 999999.0 # If no budget defined, assume unlimited
    
    # 3. Sum approved and processing amounts for this department/category/period
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
        AND LOWER(category) = ? 
        AND strftime('%Y-%m', date) = ? 
        AND status IN ('approved', 'processing')
    """
    
    params = list(dept_employees) + [category, period]
    c.execute(query, params)
    sum_row = c.fetchone()
    total_spent = sum_row[0] if sum_row and sum_row[0] else 0.0
    
    conn.close()
    
    if (total_spent + claim_amount) > cap_amount:
        return {"budget_status": "over_budget"}
    else:
        return {"budget_status": "within_budget"}
