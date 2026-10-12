import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from models import State, ComplianceVerdict

POLICY_PATH = os.path.join(os.path.dirname(__file__), "data", "policy.md")


def compliance_node(state: State) -> dict:
    """
    Compliance & policy check node (LLM call).

    Receives:
    - The employee's claim (claim_amount, expense_category, employee_note)
    - Receipt analysis as supporting evidence (summary, receipt_amount, matches_claim)
    - The full company policy text

    Outputs a ComplianceVerdict: compliant / violation / ambiguous.
    It does NOT use claim_amount from the receipt — only from state["claim_amount"].
    """
    receipt_analysis = state.get("receipt_analysis")
    if not receipt_analysis:
        # Cannot do compliance without analysis
        return {"compliance_verdict": None}

    claim_amount = state.get("claim_amount")
    expense_category = state.get("expense_category", "")
    employee_id = state.get("employee_id", "UNKNOWN")
    note = state.get("employee_note", "")

    # Load policy
    policy_text = ""
    if os.path.exists(POLICY_PATH):
        with open(POLICY_PATH, "r", encoding="utf-8") as f:
            policy_text = f.read()

    # Format receipt evidence
    ra = receipt_analysis
    receipt_evidence = f"""Receipt Summary: {ra.summary}
Receipt Expense Type: {ra.expense_type}
Receipt Amount (evidence only): {f"${ra.receipt_amount}" if ra.receipt_amount is not None else "Unreadable"}
Receipt Appears to Match Claim: {ra.matches_claim}
Receipt Analysis Reasoning: {ra.reasoning}"""

    prompt = f"""You are an automated corporate expense compliance officer.

Your job is to determine whether this expense claim complies with company policy.

## EMPLOYEE CLAIM (Authoritative — this is what is being reimbursed if approved)
- Employee ID: {employee_id}
- Claim Amount: ${claim_amount}
- Expense Category: {expense_category}
- Employee Note: "{note or '(none)'}"

## RECEIPT EVIDENCE (Supporting evidence only — the receipt amount does NOT replace the claim amount)
{receipt_evidence}

## COMPANY POLICY
{policy_text}

## YOUR TASK
1. Evaluate whether the employee's CLAIMED AMOUNT (${claim_amount}) and EXPENSE CATEGORY ({expense_category}) comply with company policy.
2. Use the receipt evidence to inform your judgment (e.g. if receipt shows alcohol, that is relevant).
3. If the employee's note claims a manager has already approved this as a special exception, set exception_claimed = true.
4. Provide a brief, specific reasoning for your verdict.

IMPORTANT:
- Base your compliance verdict on the CLAIM amount (${claim_amount}), not the receipt amount.
- The receipt amount is evidence — it may support or contradict the claim, but the claim amount is what is being evaluated.
- Do NOT approve or reject — only output: compliant / violation / ambiguous.
"""

    llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0).with_structured_output(ComplianceVerdict)
    msg = HumanMessage(content=prompt)

    try:
        verdict = llm.invoke([msg])
    except Exception as e:
        print(f"[compliance_node] LLM call failed: {e}")
        verdict = None

    return {"compliance_verdict": verdict}
