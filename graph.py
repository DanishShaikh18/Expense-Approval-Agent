from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import os

os.environ["LANGGRAPH_STRICT_MSGPACK"] = "false"

from models import State
from extraction import analysis_node
from pattern_check import pattern_check_node
from compliance import compliance_node
from budget_check import budget_check_node
from database import write_audit_record, update_receipt_status

# ---------------------------------------------------------
# Graph Nodes & Logic
# ---------------------------------------------------------

def route_join_node(state: State) -> dict:
    """
    Join node that runs after parallel branches.
    """
    return {}

def post_route_edge(state: State) -> str:
    """
    Priority-ordered routing logic based on the parallel nodes' output.
    Returns the next node: 'human_review' or 'finalize'
    """
    cv = state.get("compliance_verdict")
    match_type = state.get("match_type")
    anomalous = state.get("anomalous")
    budget_status = state.get("budget_status")
    
    # 1. Exception Claimed
    if cv and cv.exception_claimed:
        return "human_review"
        
    # 2. Exact Match
    if match_type == "exact_match":
        return "finalize" # auto-reject
        
    # 3. Possible Match or Anomalous
    if match_type == "possible_match" or anomalous:
        return "human_review"
        
    # 4. Over Budget
    if budget_status == "over_budget":
        return "human_review"
        
    # 5. Policy Violation
    if cv and cv.verdict == "violation":
        return "finalize" # auto-reject
        
    # 6. Compliant & Clean
    if cv and cv.verdict == "compliant":
        return "finalize" # auto-approve
        
    # 7. Ambiguous or Fallback
    return "human_review" 

def finalize_node(state: State) -> dict:
    """
    Transitions status from processing to approved or rejected,
    and writes the audit record.
    """
    decision = state.get("final_decision")
    reasoning = state.get("final_reasoning")
    
    # If decision is not set by human_review, auto-derive it
    if not decision:
        cv = state.get("compliance_verdict")
        match_type = state.get("match_type")
        
        if match_type == "exact_match":
            decision = "reject"
            reasoning = "Auto-rejected: Exact duplicate receipt detected."
        elif cv and cv.verdict == "violation":
            decision = "reject"
            reasoning = f"Auto-rejected: Policy violation. {cv.reasoning}"
        else:
            decision = "approve"
            reasoning = "Auto-approved: Fully compliant and within limits."
    
    # Update state for audit logger
    state["final_decision"] = decision
    state["final_reasoning"] = reasoning
    
    # Write audit log
    write_audit_record(state)
    
    # Update the receipts_index status
    db_status = "approved" if decision == "approve" else "rejected"
    update_receipt_status(state.get("receipt_id"), db_status)
    
    return {
        "final_decision": decision,
        "final_reasoning": reasoning
    }

def human_review_dummy_node(state: State) -> dict:
    """
    Dummy node for the human interrupt.
    The graph pauses BEFORE this node.
    """
    return {}

# ---------------------------------------------------------
# Graph Assembly
# ---------------------------------------------------------

workflow = StateGraph(State)

# Add nodes
workflow.add_node("analysis", analysis_node)
workflow.add_node("pattern_check", pattern_check_node)
workflow.add_node("compliance", compliance_node)
workflow.add_node("budget_check", budget_check_node)
workflow.add_node("route_join", route_join_node)
workflow.add_node("finalize", finalize_node)
workflow.add_node("human_review", human_review_dummy_node)

# Add edges
workflow.add_edge(START, "analysis")

# Direct fan-out from analysis to checks (no confidence gate)
workflow.add_edge("analysis", "pattern_check")
workflow.add_edge("analysis", "compliance")
workflow.add_edge("analysis", "budget_check")

# Parallel branches converge on route_join
workflow.add_edge("pattern_check", "route_join")
workflow.add_edge("compliance", "route_join")
workflow.add_edge("budget_check", "route_join")

# Conditional routing after join
workflow.add_conditional_edges(
    "route_join",
    post_route_edge,
    {
        "human_review": "human_review",
        "finalize": "finalize"
    }
)

# Human review goes to finalize
workflow.add_edge("human_review", "finalize")
workflow.add_edge("finalize", END)

# Setup checkpointer
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "checkpoints.sqlite")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
memory = SqliteSaver(conn)

# Compile graph with interrupt
graph = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_review"]
)
