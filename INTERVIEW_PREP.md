# Expense Approval Agent — Complete Interview Preparation Guide

> **Portfolio Project Context**:  
> This project is a focused **demonstration of stateful agentic workflow architecture** built using **LangGraph**, **Gemini Flash (Multimodal)**, and **SQLite**. It is deliberately designed to showcase core AI Engineering design patterns—graph orchestration, parallel execution (fan-out/fan-in), confidence-gated retry loops, deterministic vs. probabilistic separation, and durable human-in-the-loop (HITL) interrupts—without unnecessary over-engineering or enterprise bloat.

---

## 1. What This Project Is

The **Expense Approval Agent** is an automated workflow system that evaluates employee expense reimbursement requests (consisting of a receipt image and an optional employee explanation). 

Instead of either:
1. Routing every single expense to a human manager (manual bottleneck), or
2. Trusting a single black-box LLM prompt to make high-stakes financial decisions (hallucination risk, lack of auditability),

this system implements a **hybrid graph workflow**:
- **Probabilistic LLM tasks** are strictly confined to perception (reading messy receipt images) and natural language semantic reasoning (checking receipt items against an ambiguous company policy).
- **Deterministic business logic** (budget sums, duplicate detection, anomaly statistical baselines, and final routing decisions) is handled purely in Python and SQL.
- **Ambiguous, high-risk, or policy-exception cases** are safely halted and persisted to disk for a human manager to review and resolve asynchronously.

---

## 2. What It Does (End-to-End Walkthrough)

When an expense submission is triggered:
1. **Multimodal Extraction**: Gemini Flash reads the receipt image and employee note, producing a structured Pydantic object with receipt metadata, line items, and a legibility `confidence_score`.
2. **Confidence Gate & Retry**: If the confidence score is below 0.8, the system retries extraction (up to 2 retries). If still unreadable, it escalates directly to human review.
3. **Immediate Budget Encumbrance**: As soon as extraction succeeds, the receipt is inserted into SQLite with status `processing`. This immediately reserves the amount so concurrent or subsequent checks see the pending spend.
4. **Parallel Evaluation (Fan-Out)**: The graph splits into three concurrent branches that execute independently:
   - **`pattern_check` (Deterministic)**: Checks for exact duplicate receipts (fuzzy vendor match via `difflib` + same date + same amount), near duplicates (within 3 days), and historical spending anomalies (>3x employee's 3-month rolling average).
   - **`compliance` (LLM)**: Evaluates the itemized receipt against company policy (`data/policy.md`). Detects forbidden items (e.g., alcohol without client context), checks if the employee claimed a pre-approved exception, and provides structured reasoning.
   - **`budget_check` (Deterministic)**: Queries department budget caps and compares them against current spend (`approved` + `processing`).
5. **Synchronization & Routing (Fan-In)**: The branches converge at a join node (`route_join`). A deterministic priority router (`post_route_edge`) evaluates the combined state:
   - Any claimed exception -> **Human Review** (manager verification mandatory)
   - Exact duplicate -> **Auto-Reject**
   - Possible duplicate or Anomaly -> **Human Review**
   - Over budget -> **Human Review**
   - Explicit policy violation -> **Auto-Reject**
   - Compliant & clean -> **Auto-Approve**
   - Ambiguous / Gray area -> **Human Review**
6. **Durable Human-in-the-Loop Interrupt**: If routed to human review, LangGraph issues a checkpoint interrupt *before* entering `human_review`. The entire graph state is saved into `data/checkpoints.sqlite`. The running process exits cleanly.
7. **External Human Resumption**: A manager opens `human_review.py` in a completely separate session, reviews the pending receipt and AI reasoning, enters `approve` or `reject` with an optional note, and resumes the graph from the SQLite checkpoint.
8. **Finalization & Audit Trail**: The `finalize` node updates the receipt status to `approved` or `rejected` in `receipts_index.db` and writes an immutable, complete record into the `audit_log` table.

---

## 3. Key Architectural Features & Implementation Decisions

| Feature | How It Is Implemented | Why It Was Built This Way (Interview Talking Point) |
| :--- | :--- | :--- |
| **Separation of Concerns** | LLM used only in `extraction` and `compliance`. Plain Python/SQL used for `pattern_check`, `budget_check`, and `post_route_edge`. | LLMs are non-deterministic and poor at precise math or exact database matching. Financial checks and threshold routing must be 100% deterministic, explainable, and testable. |
| **Confidence Gate / Self-Healing Loop** | Conditional edge `check_confidence_edge` with state counter `extraction_retries`. | Prevents bad data from propagating through downstream nodes. If an image is unreadable, looping with a counter prevents infinite execution and gracefully falls back to human escalation. |
| **Fan-Out / Fan-In Parallelism** | LangGraph branches from `check_confidence_edge` to `pattern_check`, `compliance`, and `budget_check`, synchronizing at `route_join`. | These checks have zero mutual dependencies. Running them concurrently reduces end-to-end latency and mirrors real-world event-driven graph workflows. |
| **Budget Encumbrance** | `insert_processing_receipt` in `extraction_node` marks status as `processing` before running budget checks. | Solves a classic distributed race condition: if two receipts are submitted simultaneously, both would see available budget if only "approved" amounts were summed. |
| **Durable Human-in-the-Loop (HITL)** | `SqliteSaver` checkpointer with `interrupt_before=["human_review"]`. Resumed via `graph.update_state()` and `graph.invoke(None)`. | True HITL cannot rely on an in-memory `input()` statement or transient process memory. State must survive server restarts, crashes, and asynchronous manager schedules. |
| **Structured Output** | Pydantic models (`ReceiptData`, `ComplianceVerdict`) passed to `with_structured_output()`. | Eliminates brittle regex parsing and guarantees type safety when passing state across graph nodes. |
| **Explainable Audit Trail** | Dedicated `audit_log` table storing inputs, intermediate verdicts, final decision, and whether a human or machine made the call. | In AI Engineering, explainability and governance are paramount. Every automated rejection or approval must link back to specific policy reasoning. |

---

## 4. Complete Architecture & Execution Flow Diagram

```text
====================================================================================================
                                      EXPENSE APPROVAL AGENT FLOW
====================================================================================================

                                    [ START: Expense Submission ]
                                    (image_path, employee_note, etc.)
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
  (Insert into receipts_index as                                               |
       status = 'processing')                     +----------------------------+---------------------------+
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
                                                                               |   | - difflib dup| | - policy.md  | | - dept cap   |
                                                                               |   | - 3x anomaly | | - exceptions | | - spent sum  |
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
         - Ambiguous / Gray Area (Priority 7)
         - Extraction Failed >= 2 Retries
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
          (Asynchronous Manager Review via human_review.py)                        |                                                |
          - Manager inspects receipt, reasoning & verdicts                         |                                                |
          - Manager submits: approve / reject + comment                            |                                                |
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
                                            | - Writes complete immutable record (inputs, verdicts, decision, reviewer) to audit_log table |
                                            +-----------------------------------------------------------------------------------------------+
                                                                                            |
                                                                                            v
                                                                                         [ END ]
====================================================================================================
```

---

## 5. Complete Tech Stack

### Core Runtime & Frameworks
- **Python 3.11**: Primary language. Clean, functional implementation without unnecessary classes or bloated abstractions.
- **LangGraph (`langgraph`)**: Orchestrates the state graph, manages nodes, conditional edges, parallel branches, and handles durable state checkpointing.
- **LangChain Core (`langchain-core`, `langchain-google-genai`)**: Interfacing with Gemini models and configuring structured Pydantic outputs.
- **Pydantic v2**: Defines typed schemas for data extraction (`ReceiptData`, `LineItem`), policy decisions (`ComplianceVerdict`), and runtime graph state (`State`).

### Foundation Model
- **Google Gemini Flash (`gemini-3.8-flash`)**:
  - Multimodal Vision: Reads raw receipt images (Base64 JPEG/PNG) and extracts structured JSON.
  - Text Reasoning: Evaluates extracted line items against markdown policy documents.

### Storage & Persistence
- **SQLite 3 (`sqlite3`, native Python library)**:
  - `data/checkpoints.sqlite`: Used by LangGraph's `SqliteSaver` to store thread state across execution interruptions.
  - `data/receipts_index.db`: Relational tables for `receipts_index`, `budgets`, and `audit_log`.
- **Flat Files (`CSV` / `Markdown`)**:
  - `data/policy.md`: Static plain-text corporate expense guidelines.
  - `data/employee_history.csv`: Historical baseline spending data for anomaly calculations.

### Supporting Libraries
- **`difflib` (Python Standard Library)**: Implements `SequenceMatcher` for fuzzy vendor name similarity matching in duplicate detection.
- **`python-dotenv`**: Environment variable loading for `GEMINI_API_KEY`.
- **`Pillow` (`PIL`)**: Used strictly for generating synthetic benchmark receipt images for testing scenarios.

---

## 6. Codebase File Structure

```text
Expense-Approval-Agent/
├── data/
│   ├── policy.md               # Company expense policy rules
│   ├── employee_history.csv    # 3-month employee baseline spend history
│   ├── receipts_index.db       # Business SQLite DB (receipts, budgets, audit_log)
│   ├── checkpoints.sqlite      # LangGraph state checkpoint database
│   └── seed_db.py              # Script to seed initial DB tables and budgets
├── receipts/                   # Synthetic receipt test images
├── models.py                   # Pydantic schemas & TypedDict State definition
├── extraction.py               # Node 1: Vision LLM extraction & encumbrance
├── pattern_check.py            # Node 2: Deterministic duplicate & anomaly check
├── compliance.py               # Node 3: LLM policy compliance check
├── budget_check.py             # Node 4: Deterministic SQL budget cap check
├── graph.py                    # Graph assembly, conditional edges, & checkpointer
├── human_review.py             # CLI manager interface to inspect & resume threads
├── main.py                     # Test harness to execute benchmark scenarios
├── Plan.md                     # Architectural specification & engineering notes
└── README.md                   # Project overview and run instructions
```
