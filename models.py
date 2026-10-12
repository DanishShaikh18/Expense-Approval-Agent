from typing import TypedDict, Optional, Literal
from pydantic import BaseModel, Field

# Valid expense categories the employee can choose from
EXPENSE_CATEGORIES = ["Dinner", "Client Meeting", "Travel", "Office Supplies", "Accommodation", "Other"]


class ReceiptAnalysis(BaseModel):
    """
    Structured output from the Claim / Receipt Analysis node.
    This is EVIDENCE only — it never replaces the employee's claim_amount.
    """
    summary: str = Field(
        description="What the receipt appears to show (vendor, type of expense, context)."
    )
    expense_type: str = Field(
        description="Type of expense the receipt appears to represent (e.g. restaurant meal, taxi, hotel)."
    )
    receipt_amount: Optional[float] = Field(
        default=None,
        description="Amount visible on the receipt. None if unreadable. EVIDENCE ONLY — never used as the reimbursement claim."
    )
    matches_claim: bool = Field(
        description="Whether the receipt appears reasonably consistent with the employee's stated claim."
    )
    reasoning: str = Field(
        description="Short explanation of why the receipt supports or does not support the employee's claim."
    )


class ComplianceVerdict(BaseModel):
    """Structured verdict from the compliance and policy check."""
    verdict: Literal["compliant", "violation", "ambiguous"] = Field(
        description="The compliance status of the expense claim."
    )
    exception_claimed: bool = Field(
        description="True if the employee's note claims a manager already approved this as an exception."
    )
    reasoning: str = Field(description="Plain-text reasoning for the verdict.")


class State(TypedDict):
    """The flat state dictionary for the LangGraph workflow."""
    # --- Employee inputs (set once at submission, never overwritten) ---
    receipt_id: str
    employee_id: str
    claim_amount: float          # AUTHORITATIVE reimbursement amount — never overwritten
    expense_category: str        # Employee-chosen category (e.g. "Dinner")
    employee_note: str           # Optional justification text
    image_path: str              # Path to the uploaded receipt image

    # --- Set by Claim / Receipt Analysis node ---
    receipt_analysis: Optional[ReceiptAnalysis]

    # --- Set by Pattern Check node ---
    match_type: Optional[Literal["exact_match", "possible_match", "no_match"]]
    anomalous: Optional[bool]

    # --- Set by Budget Check node ---
    budget_status: Optional[Literal["within_budget", "over_budget"]]

    # --- Set by Compliance node ---
    compliance_verdict: Optional[ComplianceVerdict]

    # --- Set by Human Review or Finalize ---
    final_decision: Optional[Literal["approve", "reject"]]
    final_reasoning: Optional[str]
    human_review_comment: Optional[str]
