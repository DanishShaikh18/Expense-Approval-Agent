# Expense Approval Agent (Graph Workflow Demo)

A portfolio project demonstrating a stateful, graph-based agent architecture using LangGraph. It processes employee expense submissions (a receipt image and a short explanation) to showcase parallel execution branches (fan-out/fan-in), confidence-gated retry loops, deterministic vs. probabilistic separation, and durable human-in-the-loop (HITL) checkpoints.

---

## What It Is & How It Works

When an expense is submitted, the system runs a predefined workflow:

1. **Extraction**: Gemini Flash reads the receipt image and note, outputting structured data (vendor, date, items, total, alcohol presence) and a legibility `confidence_score`.
2. **Confidence Gate**: If extraction confidence is low (< 0.8), it loops back to retry (up to 2 retries). If still unreadable, it escalates to human review.
3. **Budget Encumbrance**: Once extracted, the receipt is inserted into SQLite with status `processing` to reserve funds immediately.
4. **Parallel Analysis (Fan-out)**: The data splits into three simultaneous, independent tracks:
   - **Pattern Check** (Deterministic Python): Checks for duplicate receipts using `difflib` string similarity and date matching, and flags spending anomalies (>3x rolling 3-month baseline).
   - **Compliance Check** (LLM): Evaluates line items against `data/policy.md` and detects whether the employee claimed a pre-approved manager exception.
   - **Budget Check** (Deterministic SQL): Checks the employee's department and category budget cap against current spend (`approved` + `processing`).
5. **Routing (Join & Fan-in)**: All 3 branches synchronize at `route_join`. A deterministic router applies priority rules (e.g., claimed exceptions and budget overruns go to human review; exact duplicates and policy violations are auto-rejected; clean expenses are auto-approved).
6. **Human Review**: If escalated, LangGraph suspends execution using SQLite checkpoints (`data/checkpoints.sqlite`). A manager can later review the receipt and AI reasoning via a CLI script (`human_review.py`) and resume the workflow.
7. **Finalize**: Updates receipt status in `receipts_index.db` and writes an immutable trail to `audit_log`.

---

## Graph Architecture

```text
                                [ START: Expense Submission ]
                                               |
                                               v
                                 +---------------------------+
                                 |      extraction_node      |
                                 |  (Gemini Flash Multimodal)|
                                 +---------------------------+
                                               |
                +------------------------------+-----------------------------+
                |                                                            |
                v                                                            v
    [ Encumber Budget in DB ]                                      { check_confidence_edge }
(Insert into receipts_index as                                                 |
     status = 'processing')                       +----------------------------+---------------------------+
                                                |                            |                           |
                                    (conf < 0.8 & retries < 2)   (conf < 0.8 & retries >= 2)     (conf >= 0.8)
                                                |                            |                           |
                                                v                            |                           v
                                      [ Retry Extraction ]                   |              +-------------------------+
                                      (Loops back to node)                   |              |   FAN-OUT IN PARALLEL   |
                                                                             |              +-------------------------+
                                                                             |                |          |          |
                                                                             |         +------+          |          +------+
                                                                             |         |                 |                 |
                                                                             |         v                 v                 v
                                                                             |   +--------------+ +--------------+ +--------------+
                                                                             |   |pattern_check | |  compliance  | | budget_check |
                                                                             |   | (Python/SQL) | | (Gemini LLM) | | (SQL Query)  |
                                                                             |   +--------------+ +--------------+ +--------------+
                                                                             |         |                 |                 |
                                                                             |         +------+          |          +------+
                                                                             |                |          |          |
                                                                             |                v          v          v
                                                                             |              +-------------------------+
                                                                             |              |     route_join_node     |
                                                                             |              | (Fan-In Synchronization)|
                                                                             |              +-------------------------+
                                                                             |                            |
                                                                             |                            v
                                                                             |                 { post_route_edge }
                                                                             |              (Deterministic Priority)
                                                                             |                            |
                                +--------------------------------------------+   +------------------------+-----------------------+
                                |                                                |                                                |
               [ Needs Human Verification ]                        [ Auto-Reject ]                                  [ Auto-Approve ]
       - Exception Claimed (Priority 1)                     - Exact Duplicate Match (Priority 2)             - Compliant & Clean (Priority 6)
       - Possible Match / Spending Anomaly (Priority 3)     - Policy Violation (Priority 5)
       - Over Budget (Priority 4)
       - Ambiguous Policy (Priority 7)
       - Low Extraction Confidence >= 2 Retries
                                |                                                |                                                |
                                v                                                |                                                |
       ====================================================                      |                                                |
        HUMAN-IN-THE-LOOP INTERRUPT (LangGraph)                                  |                                                |
        - Execution paused BEFORE 'human_review' node                            |                                                |
        - Full state persisted to 'data/checkpoints.sqlite'                      |                                                |
        - Process exits cleanly                                                  |                                                |
       ====================================================                      |                                                |
                                |                                                |                                                |
                                v                                                |                                                |
        (Manager Review via human_review.py)                                     |                                                |
        - Manager enters decision (approve / reject)                             |                                                |
        - graph.update_state() + graph.invoke(None)                              |                                                |
                                |                                                |                                                |
                                v                                                |                                                |
                 +-----------------------------+                                 |                                                |
                 |   human_review_dummy_node   |                                 |                                                |
                 +-----------------------------+                                 |                                                |
                                |                                                |                                                |
                                +-----------------------+                        |                                                |
                                                        |                        |                                                |
                                                        v                        v                                                v
                                          +-----------------------------------------------------------------------------------------------+
                                          |                                         finalize_node                                         |
                                          | - Updates receipt status to 'approved' or 'rejected' in receipts_index                        |
                                          | - Writes complete record (inputs, verdicts, decision, reviewer) to audit_log table            |
                                          +-----------------------------------------------------------------------------------------------+
                                                                                          |
                                                                                          v
                                                                                       [ END ]
```

---

## Node Breakdown

1. **`extraction_node`**: Uses Gemini Flash to read receipt images and output typed JSON (`ReceiptData`) via Pydantic. Inserts the record as `processing` to encumber budget.
2. **`check_confidence_edge`**: Conditional edge that loops back to retry extraction or escalates to human review if image legibility is low.
3. **`pattern_check_node`**: Deterministic Python check using `difflib.SequenceMatcher` for vendor similarity and a rolling 3-month average for spending anomalies.
4. **`compliance_node`**: Evaluates line items and employee notes against `data/policy.md` via Gemini Flash structured output.
5. **`budget_check_node`**: Deterministic SQL query calculating department spend against budget caps.
6. **`route_join_node`**: Synchronization point for the 3 parallel branches.
7. **`human_review_dummy_node`**: Pause target for LangGraph's checkpointer.
8. **`finalize_node`**: Writes the audit log and updates receipt status.

---

## Tech Stack

- **Python 3.11**
- **LangGraph & LangChain** (`langgraph`, `langchain-core`, `langchain-google-genai`)
- **Google Gemini Flash (`gemini-3.8-flash`)**
- **SQLite** (`data/checkpoints.sqlite` and `data/receipts_index.db`)
- **Pydantic v2**
- **difflib & csv** (Standard library)
- **python-dotenv**

---

## Getting Started

### 1. Setup Environment
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API Key
Create a `.env` file in the root directory and add your Gemini API Key:
```env
GEMINI_API_KEY="your_api_key_here"
```

### 3. Initialize the Database
Seed the SQLite database with baseline spending history, past receipts, and budget caps:
```bash
python data/seed_db.py
```

### 4. Submit an Expense
Submit an expense interactively:
```bash
python main.py
```
Or specify submission details directly via command-line arguments:
```bash
python main.py --image receipts/Starbuck_Receipt.jpeg --employee EMP001 --note "Morning coffee before client call"
```

### 5. Resume Paused Graphs
If any expenses pause for human review, launch the review CLI:
```bash
python human_review.py
```