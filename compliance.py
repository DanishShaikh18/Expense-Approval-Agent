from models import State, ComplianceVerdict

def compliance_node(state: State) -> dict:
    """
    MOCKED Compliance & risk check node (LLM call).
    Returns predefined ComplianceVerdict based on the test scenario's receipt_id
    since the LLM API key is not yet configured.
    """
    receipt_id = state.get("receipt_id", "")
    note = state.get("employee_note", "").lower()
    
    # Check if note claims exception (this is usually LLM parsed, but we'll mock it based on note text)
    exception_claimed = "approved" in note or "exception" in note

    verdict_status = "compliant"
    reasoning = "Expense appears normal and within policy limits."

    if receipt_id == "TEST-01-CLEAN":
        verdict_status = "compliant"
    elif receipt_id == "TEST-02-VIOLATION":
        verdict_status = "violation"
        reasoning = "Personal items (video games) are never reimbursable."
    elif receipt_id == "TEST-05-AMBIGUOUS-APP":
        verdict_status = "ambiguous"
        reasoning = "Alcohol is present but it's unclear if an external client was attending."
    elif receipt_id == "TEST-06-AMBIGUOUS-REJ":
        verdict_status = "ambiguous"
        reasoning = "Team celebration alcohol claim without clear client presence."
    elif receipt_id == "TEST-07-EXCEPTION":
        verdict_status = "violation"
        reasoning = "Software over $200 requires pre-approval."

    # If the employee specifically claims an exception, the LLM should flag it
    if exception_claimed:
        exception_claimed = True

    return {
        "compliance_verdict": ComplianceVerdict(
            verdict=verdict_status,
            exception_claimed=exception_claimed,
            reasoning=reasoning
        )
    }
