from typing import TypedDict, Optional, Literal, List
from pydantic import BaseModel, Field

class LineItem(BaseModel):
    description: str
    amount: float

class ReceiptData(BaseModel):
    """Structured data extracted from the receipt image."""
    vendor: str = Field(description="Name of the vendor or merchant")
    date: str = Field(description="Date of the expense in YYYY-MM-DD format")
    total_amount: float = Field(description="Total amount of the expense")
    line_items: List[LineItem] = Field(description="Individual items on the receipt")
    alcohol_appears: bool = Field(description="True if alcohol appears on the receipt")
    confidence_score: float = Field(description="Confidence score (0.0 to 1.0) of the extraction legibility")

class ComplianceVerdict(BaseModel):
    """Structured verdict from the compliance and risk check."""
    verdict: Literal["compliant", "violation", "ambiguous"] = Field(
        description="The compliance status of the expense"
    )
    exception_claimed: bool = Field(
        description="True if the employee's note claims a manager already approved this as an exception"
    )
    reasoning: str = Field(description="Plain-text reasoning for the verdict")

class State(TypedDict):
    """The flat state dictionary for the LangGraph workflow."""
    receipt_id: str
    employee_id: str
    image_path: str
    employee_note: str
    
    # State updated by Extraction node
    extraction_retries: int
    receipt_data: Optional[ReceiptData]
    
    # State updated by Duplicate Check node
    duplicate_match: Optional[Literal["exact_match", "possible_match", "no_match"]]
    
    # State updated by Compliance node
    compliance_verdict: Optional[ComplianceVerdict]
    
    # Final decisions (updated by Route, Human Review, or Finalize nodes)
    final_decision: Optional[Literal["approve", "reject"]]
    final_reasoning: Optional[str]
    human_review_comment: Optional[str]
