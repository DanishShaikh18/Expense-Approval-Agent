import sqlite3
import os
from dotenv import load_dotenv
load_dotenv()

from graph import graph, conn

def get_pending_threads():
    """Queries the SQLite checkpointer for threads that might be paused."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
        threads = cursor.fetchall()
        return [t[0] for t in threads]
    except sqlite3.OperationalError:
        return []

def run_human_review():
    print("--- Human Review Manager ---")
    threads = get_pending_threads()
    
    if not threads:
        print("No active threads found.")
        return
        
    pending_found = False
    
    for thread_id in threads:
        config = {"configurable": {"thread_id": thread_id}}
        state_snap = graph.get_state(config)
        
        # Check if this thread is paused before 'human_review'
        if state_snap and "human_review" in state_snap.next:
            pending_found = True
            state = state_snap.values
            ra = state.get('receipt_analysis')
            cv = state.get('compliance_verdict')
            match_type = state.get('match_type')
            anomalous = state.get('anomalous')
            budget_status = state.get('budget_status')
            
            print("\n" + "="*50)
            print(f"REVIEW NEEDED FOR RECEIPT: {state.get('receipt_id')}")
            print(f"Employee: {state.get('employee_id')}")
            print(f"Claim Amount: ${state.get('claim_amount')} (AUTHORITATIVE)")
            print(f"Expense Category: {state.get('expense_category')}")
            print(f"Note: {state.get('employee_note')}")
            print("-" * 20)
            if ra:
                print(f"Receipt Analysis Summary: {ra.summary}")
                print(f"Receipt Expense Type: {ra.expense_type}")
                print(f"Receipt Amount (evidence only): ${ra.receipt_amount if ra.receipt_amount is not None else 'Unreadable'}")
                print(f"Matches Claim: {ra.matches_claim}")
                print(f"Analysis Reasoning: {ra.reasoning}")
            else:
                print("No receipt analysis available.")
            print("-" * 20)
            print(f"Pattern Match: {match_type} | Spending Anomaly: {anomalous}")
            print(f"Budget Status: {budget_status}")
            if cv:
                print(f"Compliance verdict: {cv.verdict.upper()}")
                print(f"Exception claimed: {cv.exception_claimed}")
                print(f"Reasoning: {cv.reasoning}")
            print("="*50)
            
            decision = ""
            while decision not in ["approve", "reject", "skip"]:
                decision = input("Decision (approve/reject/skip): ").strip().lower()
                
            if decision == "skip":
                continue
                
            comment = input("Optional comment: ").strip()
            
            # Update the state with the human decision
            print(f"Updating state and resuming graph for {thread_id}...")
            
            graph.update_state(
                config,
                {
                    "final_decision": decision,
                    "final_reasoning": f"Human review decision: {decision}",
                    "human_review_comment": comment
                },
                as_node="human_review"
            )
            
            # Resume the graph
            graph.invoke(None, config)
            print(f"[OK] Finished processing {thread_id}")

    if not pending_found:
        print("No expenses currently waiting for human review.")

if __name__ == "__main__":
    run_human_review()
