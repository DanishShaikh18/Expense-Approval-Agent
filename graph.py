from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import os

from models import State
from extraction import extraction_node
from duplicate_check import duplicate_check_node
from compliance import compliance_node
from database import write_audit_record

# ---------------------------------------------------------
# Graph Nodes & Logic
# ---------------------------------------------------------

def check_confidence_edge(state: State) -> list[str]:
    """Confidence gate conditional edge."""
    rd = state.get("receipt_data")
    retries = state.get("extraction_retries", 0)
    
    if rd and rd.confidence_score < 0.8:
        if retries < 2:
            return ["extraction"] # Loop back
        else:
            return ["human_review"] # Escalate
    
    # Fan out to parallel nodes
    return ["duplicate_check", "compliance"]

def route_join_node(state: State) -> dict:
    """
    Join node that runs after duplicate_check and compliance.
    We don't need to return much, just pass through. 
    The logic will be evaluated in the conditional edge next.
    """
    return {}

def post_route_edge(state: State) -> str:
    """
    Priority-ordered routing logic based on the parallel nodes' output.
    Returns the next node: 'human_review' or 'finalize'
    """
    cv = state.get("compliance_verdict")
    dup = state.get("duplicate_match")
    
    if cv and cv.exception_claimed:
        return "human_review"
    if dup == "exact_match":
        return "finalize" # auto-reject (will be set in finalize or here)
    if dup == "possible_match":
        return "human_review"
    
    if dup == "no_match" and cv:
        if cv.verdict == "violation":
            return "finalize" # auto-reject
        if cv.verdict == "compliant":
            return "finalize" # auto-approve
        if cv.verdict == "ambiguous":
            return "human_review"
            
    return "human_review" # Fallback

def prepare_finalize_node(state: State) -> dict:
    """
    Prepares the final decision if it was auto-resolved.
    If it came from human_review, the decision is already in the state.
    """
    # If a manager already made a decision, keep it.
    if state.get("final_decision"):
        return {}
        
    cv = state.get("compliance_verdict")
    dup = state.get("duplicate_match")
    
    decision = None
    reasoning = None
    
    if dup == "exact_match":
        decision = "reject"
        reasoning = "Auto-rejected: Exact duplicate receipt detected."
    elif cv and cv.verdict == "violation":
        decision = "reject"
        reasoning = f"Auto-rejected: Policy violation. {cv.reasoning}"
    elif cv and cv.verdict == "compliant" and dup == "no_match":
        decision = "approve"
        reasoning = "Auto-approved: Fully compliant."
        
    return {
        "final_decision": decision,
        "final_reasoning": reasoning
    }

def finalize_node(state: State) -> dict:
    """Writes the audit record."""
    write_audit_record(state)
    return {}

def human_review_dummy_node(state: State) -> dict:
    """
    Dummy node for the human interrupt.
    The graph pauses BEFORE this node (or we can just pause on it).
    We will configure the checkpointer to interrupt BEFORE 'human_review'.
    """
    return {}

# ---------------------------------------------------------
# Graph Assembly
# ---------------------------------------------------------

workflow = StateGraph(State)

# Add nodes
workflow.add_node("extraction", extraction_node)
workflow.add_node("duplicate_check", duplicate_check_node)
workflow.add_node("compliance", compliance_node)
workflow.add_node("route_join", route_join_node)
workflow.add_node("prepare_finalize", prepare_finalize_node)
workflow.add_node("finalize", finalize_node)
workflow.add_node("human_review", human_review_dummy_node)

# Add edges
workflow.add_edge(START, "extraction")

# Conditional fan-out from extraction
workflow.add_conditional_edges(
    "extraction",
    check_confidence_edge,
    {
        "extraction": "extraction",
        "human_review": "human_review",
        "duplicate_check": "duplicate_check",
        "compliance": "compliance"
    }
)

# Parallel branches converge on route_join
workflow.add_edge("duplicate_check", "route_join")
workflow.add_edge("compliance", "route_join")

# Conditional routing after join
workflow.add_conditional_edges(
    "route_join",
    post_route_edge,
    {
        "human_review": "human_review",
        "finalize": "prepare_finalize"
    }
)

# Human review goes to finalize
workflow.add_edge("human_review", "prepare_finalize")

# Prepare finalize goes to finalize
workflow.add_edge("prepare_finalize", "finalize")
workflow.add_edge("finalize", END)

# Setup checkpointer
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "checkpoints.sqlite")
# Ensure the directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
memory = SqliteSaver(conn)

# Compile graph with interrupt
graph = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_review"]
)
