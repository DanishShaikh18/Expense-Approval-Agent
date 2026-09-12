import sqlite3
import os
import time
from dotenv import load_dotenv
load_dotenv()

from graph import graph
from database import DB_PATH

def print_audit_log():
    print("\n--- AUDIT LOG ---")
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT receipt_id, duplicate_match, compliance_verdict, final_decision FROM audit_log")
        rows = c.fetchall()
        for r in rows:
            print(f"{r[0]:<22} | Dup: {str(r[1]):<14} | Comp: {str(r[2]):<10} | Final: {str(r[3])}")
    except sqlite3.OperationalError:
        print("Audit log empty or not created yet.")
    conn.close()
    print("-----------------\n")

def run_scenario(scenario_id, desc, thread_id, employee_id, note, image_path):
    print(f"\n[{scenario_id}] {desc}")
    config = {"configurable": {"thread_id": thread_id}}
    
    # Check if this thread was already started and paused
    snap = graph.get_state(config)
    if snap and "human_review" in snap.next:
        print("This scenario is currently paused for human review. Run human_review.py.")
        return
        
    if snap and not snap.next and snap.values.get("final_decision"):
        print(f"Already completed with decision: {snap.values.get('final_decision')}")
        return

    initial_state = {
        "receipt_id": scenario_id,
        "employee_id": employee_id,
        "employee_note": note,
        "image_path": image_path,
        "extraction_retries": 0
    }
        
    print(f"Invoking graph with image: {image_path}...")
    result = graph.invoke(initial_state, config=config)
    
    snap = graph.get_state(config)
    if snap and "human_review" in snap.next:
        print(f"[PAUSED] Graph execution paused. Waiting for human review.")
    else:
        print(f"[OK] Auto-resolved! Final Decision: {result.get('final_decision')}")
        print(f"Reasoning: {result.get('final_reasoning')}")

def main():
    scenarios = [
        (
            "REAL-TEST-01",
            "Starbucks coffee receipt - should be compliant",
            "EMP001",
            "Morning coffee before client call",
            "receipts/Starbuck_Receipt.jpeg"
        ),
        (
            "REAL-TEST-02",
            "Restaurant dinner receipt - could be ambiguous or auto-approved depending on LLM interpretation",
            "EMP005",
            "Client dinner with John Doe (Acme Corp)",
            "receipts/Restaurant-Receipt.png"
        )
    ]
    
    print("Running Real LLM Test Scenarios...")
    for s_id, desc, emp, note, img in scenarios:
        run_scenario(s_id, desc, f"thread_{s_id}", emp, note, img)
        # short pause to prevent rate limit
        time.sleep(2)

    print("\nInitial runs complete. Run 'python human_review.py' to unblock paused tests.")
    print_audit_log()

if __name__ == "__main__":
    main()
