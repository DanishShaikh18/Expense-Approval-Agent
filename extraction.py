from models import State, ReceiptData, LineItem

def extraction_node(state: State) -> dict:
    """
    MOCKED Extraction node logic (Vision LLM call).
    Returns predefined ReceiptData based on the test scenario's receipt_id
    since the LLM API key is not yet configured.
    """
    receipt_id = state.get("receipt_id", "")
    retries = state.get("extraction_retries", 0)
    
    # Base clean data
    data = ReceiptData(
        vendor="Acme Supplies",
        date="2025-10-01",
        total_amount=20.00,
        line_items=[LineItem(description="Office Supplies", amount=20.00)],
        alcohol_appears=False,
        confidence_score=0.95
    )

    if receipt_id == "TEST-01-CLEAN":
        data.vendor = "CleanVendor"
    elif receipt_id == "TEST-02-VIOLATION":
        data.vendor = "Gaming Store"
        data.line_items = [LineItem(description="Video Game (Personal)", amount=60.00)]
        data.total_amount = 60.00
    elif receipt_id == "TEST-03-EXACT-DUP":
        # Matches RCP-003 exactly
        data.vendor = "Coursera"
        data.date = "2025-07-07"
        data.total_amount = 299.00
    elif receipt_id == "TEST-04-POSSIBLE-DUP":
        # Similar to RCP-011 but not exact amount, but we'll fake the image hash in duplicate_check
        data.vendor = "RPM Steakhouse"
        data.date = "2025-07-09"
        data.total_amount = 89.40 # RCP-011 was 87.40
    elif receipt_id == "TEST-05-AMBIGUOUS-APP":
        data.vendor = "Local Pub"
        data.alcohol_appears = True
        data.total_amount = 120.00
    elif receipt_id == "TEST-06-AMBIGUOUS-REJ":
        data.vendor = "Downtown Bar"
        data.alcohol_appears = True
        data.total_amount = 140.00
    elif receipt_id == "TEST-07-EXCEPTION":
        data.vendor = "Expensive Software"
        data.total_amount = 800.00
    elif receipt_id == "TEST-08-BLURRY":
        if retries < 2:
            data.confidence_score = 0.4 # Low confidence
        else:
            data.confidence_score = 0.9 # Succeeds after retries
            
    return {
        "receipt_data": data,
        "extraction_retries": retries + 1
    }
