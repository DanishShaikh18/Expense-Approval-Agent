import os
import uuid
import argparse
from dotenv import load_dotenv
load_dotenv()

from graph import graph

def process_expense(receipt_id: str, employee_id: str, image_path: str, employee_note: str = "") -> dict:
    """
    Submits an expense to the LangGraph workflow and runs it until completion or human interrupt.
    """
    if not os.path.exists(image_path):
        print(f"Error: Receipt image not found at '{image_path}'")
        return {}

    thread_id = f"thread_{receipt_id}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "receipt_id": receipt_id,
        "employee_id": employee_id,
        "employee_note": employee_note,
        "image_path": image_path,
        "extraction_retries": 0
    }

    print(f"\n--- Submitting Expense [{receipt_id}] ---")
    print(f"Employee ID  : {employee_id}")
    print(f"Receipt Image: {image_path}")
    print(f"Employee Note: {employee_note or '(None)'}")
    print("Processing through LangGraph workflow...\n")

    result = graph.invoke(initial_state, config=config)

    # Check whether the graph paused at human review or completed
    snap = graph.get_state(config)
    if snap and "human_review" in snap.next:
        print("[STATUS: PAUSED] Expense flagged for Human Review.")
        print("Reason: Flagged by policy ambiguity, budget limit, spending anomaly, or claimed exception.")
        print("Action: Run 'python human_review.py' to review and resolve this expense.")
    else:
        decision = result.get("final_decision", "Unknown")
        reasoning = result.get("final_reasoning", "No reasoning provided.")
        print(f"[STATUS: COMPLETED] Final Decision: {decision.upper()}")
        print(f"Reasoning: {reasoning}")

    return result

def main():
    parser = argparse.ArgumentParser(description="Expense Approval Agent")
    parser.add_argument("--image", type=str, help="Path to receipt image", default=None)
    parser.add_argument("--employee", type=str, help="Employee ID (e.g. EMP001)", default=None)
    parser.add_argument("--note", type=str, help="Employee note or justification", default="")
    parser.add_argument("--id", type=str, help="Custom Receipt ID", default=None)

    args = parser.parse_args()

    # Interactive prompts if CLI arguments are not provided
    image_path = args.image
    if not image_path:
        default_img = "receipts/Starbuck_Receipt.jpeg"
        user_val = input(f"Enter receipt image path [default: {default_img}]: ").strip()
        image_path = user_val if user_val else default_img

    employee_id = args.employee
    if not employee_id:
        default_emp = "EMP001"
        user_val = input(f"Enter employee ID [default: {default_emp}]: ").strip()
        employee_id = user_val if user_val else default_emp

    note = args.note
    if not note and not args.employee:
        note = input("Enter employee note (optional): ").strip()

    receipt_id = args.id or f"EXP-{uuid.uuid4().hex[:6].upper()}"

    process_expense(
        receipt_id=receipt_id,
        employee_id=employee_id,
        image_path=image_path,
        employee_note=note
    )

if __name__ == "__main__":
    main()
