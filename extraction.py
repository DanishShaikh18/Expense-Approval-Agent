import base64
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from models import State, ReceiptAnalysis
from database import insert_processing_receipt


def analysis_node(state: State) -> dict:
    """
    Claim / Receipt Analysis node (Multimodal LLM call).

    Purpose: understand what the employee is claiming and inspect the receipt
    image as supporting evidence. This node produces a ReceiptAnalysis object.

    It does NOT:
    - decide policy compliance
    - decide whether to approve or reject
    - replace claim_amount with the receipt amount

    The claim_amount from state is always the authoritative reimbursement amount.
    """
    image_path = state.get("image_path", "")
    claim_amount = state.get("claim_amount")
    expense_category = state.get("expense_category", "")
    note = state.get("employee_note", "")

    if not image_path or not os.path.exists(image_path):
        raise ValueError(f"Receipt image not found at path: '{image_path}'")

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    # Detect image format from extension for the correct data URI
    ext = os.path.splitext(image_path)[1].lower()
    mime_type = "image/png" if ext == ".png" else "image/jpeg"

    prompt = f"""You are analyzing a receipt image submitted as supporting evidence for an expense claim.

EMPLOYEE CLAIM:
- Claimed Amount: {claim_amount}
- Expense Category: {expense_category}
- Employee Note: "{note or '(none)'}"

YOUR TASK:
1. Examine the receipt image carefully.
2. Describe what the receipt appears to show (vendor, type of expense, items, context).
3. Read the amount visible on the receipt if legible. If the amount is unclear or unreadable, set receipt_amount to null — do NOT guess.
4. Determine whether the receipt appears to reasonably support the employee's claim.
5. Provide a brief reasoning for your assessment.

IMPORTANT RULES:
- The employee's claimed amount ({claim_amount}) is the actual reimbursement request. Do not treat the receipt amount as the claim.
- Do NOT make company policy decisions (e.g. "this violates policy"). Only describe what you see.
- Do NOT invent or hallucinate receipt details you cannot read.
- If the receipt is unclear, say so in the summary and set receipt_amount to null.
"""

    llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0).with_structured_output(ReceiptAnalysis)

    msg = HumanMessage(content=[
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}}
    ])

    try:
        analysis = llm.invoke([msg])
    except Exception as e:
        print(f"[analysis_node] LLM call failed: {e}")
        # Provide a minimal fallback so the graph can continue
        analysis = ReceiptAnalysis(
            summary="Receipt analysis failed due to an LLM error.",
            expense_type="unknown",
            receipt_amount=None,
            matches_claim=False,
            reasoning=f"LLM error: {e}"
        )

    # Encumber budget immediately — write as 'processing' using claim_amount
    insert_processing_receipt(state, analysis)

    return {"receipt_analysis": analysis}
