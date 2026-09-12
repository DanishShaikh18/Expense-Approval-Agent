import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from models import State, ComplianceVerdict
from database import get_employee_history

POLICY_PATH = os.path.join(os.path.dirname(__file__), "data", "policy.md")

def compliance_node(state: State) -> dict:
    """
    Compliance & risk check node logic (LLM call).
    Outputs compliance verdict based on structured data, policy, and history.
    """
    receipt_data = state.get("receipt_data")
    if not receipt_data:
        # If extraction failed, we can't do compliance
        return {"compliance_verdict": None}

    employee_id = state.get("employee_id", "UNKNOWN")
    note = state.get("employee_note", "")
    
    # 1. Load the policy
    policy_text = ""
    if os.path.exists(POLICY_PATH):
        with open(POLICY_PATH, "r", encoding="utf-8") as f:
            policy_text = f.read()
            
    # 2. Get the employee history
    history_text = get_employee_history(employee_id)
    
    # 3. Format the receipt data for the prompt
    receipt_str = f"Vendor: {receipt_data.vendor}\nDate: {receipt_data.date}\nAmount: ${receipt_data.total_amount}\n"
    receipt_str += f"Alcohol present: {receipt_data.alcohol_appears}\n"
    receipt_str += "Items:\n" + "\n".join([f"- {item.description} (${item.amount})" for item in receipt_data.line_items])

    # 4. Construct prompt
    prompt = f"""
    You are an automated corporate expense compliance officer. 
    Analyze the following expense submission based strictly on the provided company policy.

    # Company Policy:
    {policy_text}

    # Employee Recent Spending History:
    {history_text}

    # Current Expense Submission:
    Employee ID: {employee_id}
    Employee Note: '{note}'
    
    # Extracted Receipt Data:
    {receipt_str}
    
    Task: 
    1. Determine if this expense is compliant, a violation, or ambiguous (gray area).
    2. Check if the employee's note explicitly claims a manager has already approved this as an exception.
    3. Provide a brief reasoning for your verdict.
    """

    llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0).with_structured_output(ComplianceVerdict)
    msg = HumanMessage(content=prompt)
    
    try:
        verdict = llm.invoke([msg])
    except Exception as e:
        print(f"Compliance LLM call failed: {e}")
        verdict = None

    return {
        "compliance_verdict": verdict
    }
