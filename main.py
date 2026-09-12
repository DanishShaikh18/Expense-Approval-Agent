from graph import graph
import sqlite3
import os
import time
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
            print(f"{r[0]:<22} | Dup: {r[1]:<14} | Comp: {r[2]:<10} | Final: {r[3]}")
    except sqlite3.OperationalError:
        print("Audit log empty or not created yet.")
    conn.close()
    print("-----------------\n")

def run_scenario(scenario_id, desc, thread_id):
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
        "employee_id": "EMP001",
        "employee_note": "Business expense",
        "image_path": "receipts/dummy.jpg",
        "extraction_retries": 0
    }
    
    if scenario_id == "TEST-07-EXCEPTION":
        initial_state["employee_note"] = "Manager approved exception for this software"
    elif scenario_id == "TEST-04-POSSIBLE-DUP":
        # Fake a duplicate image name so duplicate_check flags it
        initial_state["image_path"] = "receipts/duplicate_fake.jpg"
        
    print("Invoking graph...")
    result = graph.invoke(initial_state, config=config)
    
    snap = graph.get_state(config)
    if snap and "human_review" in snap.next:
        print(f"[PAUSED] Graph execution paused. Waiting for human review.")
    else:
        print(f"[OK] Auto-resolved! Final Decision: {result.get('final_decision')}")

def main():
    scenarios = [
        ("TEST-01-CLEAN", "Clean, obviously compliant -> auto-approve"),
        ("TEST-02-VIOLATION", "Clear policy violation -> auto-reject"),
        ("TEST-03-EXACT-DUP", "Exact duplicate -> auto-reject"),
        ("TEST-04-POSSIBLE-DUP", "Possible duplicate match -> human review"),
        ("TEST-05-AMBIGUOUS-APP", "Ambiguous (alcohol) -> human review"),
        ("TEST-06-AMBIGUOUS-REJ", "Ambiguous (alcohol) -> human review"),
        ("TEST-07-EXCEPTION", "Manager exception claimed -> human review"),
        ("TEST-08-BLURRY", "Blurry -> retries -> succeeds")
    ]
    
    print("Running Mocked LLM Test Scenarios...")
    for s_id, desc in scenarios:
        run_scenario(s_id, desc, f"thread_{s_id}")
        time.sleep(0.5)

    print("\nInitial runs complete. Run 'python human_review.py' to unblock paused tests.")
    print_audit_log()

if __name__ == "__main__":
    main()
