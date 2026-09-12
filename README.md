# Expense Approval Agent (Graph Workflow Architecture)

An advanced, AI-powered agentic workflow that automates the review, validation, and approval of corporate employee expense submissions. Instead of pushing every single expense to a human manager for manual review, this intelligent system automatically approves compliant expenses, outright rejects clear violations or duplicates, and safely escalates ambiguous or edge-case submissions to a human-in-the-loop.

This project serves as a portfolio demonstration of a **genuine graph-based agent architecture** emphasizing control, reliability, and human oversight.

---

## What It Is & How It Works

When an employee submits an expense (a receipt image and a short note), the system orchestrates a workflow that analyzes the submission across multiple dimensions:

1. **Multimodal Extraction**: A vision-capable LLM reads the receipt image and extracts highly structured data (vendor, date, items, total, and flags like alcohol presence).
2. **Quality Control**: The graph employs a confidence gate. If the AI is unsure about the receipt's legibility, it executes a self-healing retry loop (capped to prevent infinite loops) before escalating.
3. **Parallel Analysis**: Once extracted, the data splits into two simultaneous, independent validation tracks:
   - A deterministic script checks for duplicate submissions using exact metadata matching and perceptual image hashing.
   - An LLM-driven compliance engine evaluates the expense against the corporate policy and the employee's historical spending patterns.
4. **Intelligent Routing**: The graph converges and applies strict, priority-ordered business logic. If an expense is completely clean, it gets auto-approved. If there is a policy violation or an exact duplicate, it is auto-rejected. If the case is ambiguous, partially matches a duplicate, or claims a special exception, the system suspends execution.
5. **Human-in-the-Loop**: Suspended graphs are saved to a durable SQLite database. A manager can later review the AI's reasoning, input a decision, and seamlessly resume the workflow right where it left off.

---

## The Graph Architecture (Node by Node)

The architecture is built using LangGraph as a `StateGraph`, mapping the flow of data through distinct operational nodes.

- **`extraction_node` (Probabilistic)**: Uses Gemini's multimodal capabilities to "read" the receipt image and extract structured data using Pydantic. It also assigns a confidence score to its own extraction.
- **`check_confidence_edge` (Conditional Gate)**: Pure Python logic that acts as a quality gate. If the extraction confidence is low, it loops back to the extraction node for a retry. If it fails twice, it routes to a human manager.
- **`duplicate_check_node` (Deterministic)**: Never uses an LLM. It relies on standard SQL exact-match queries and `imagehash` perceptual hashing to mathematically prove if a receipt is a duplicate.
- **`compliance_node` (Probabilistic)**: Takes the extracted receipt data, the company policy document, and the employee's spending history CSV, injecting them all into a single context window. The LLM then outputs a strict `ComplianceVerdict`.
- **`route_join` (Join/Routing Gate)**: A convergence point that waits for both parallel branches to finish. It applies strict hierarchical logic (e.g., an exact duplicate overrides an "ambiguous" compliance verdict) to determine the final path.
- **`human_review_node` (Durable Interrupt)**: A dummy node where the LangGraph checkpointer is configured to suspend execution. It acts as an asynchronous pause button, allowing a manager to interject via a separate CLI interface (`human_review.py`).
- **`finalize_node` (State Mutation)**: Writes the final decision, along with the AI's reasoning and any human comments, to an SQLite audit log.

---

## AI Engineering Concepts Demonstrated

This project highlights several modern AI engineering best practices:

- **Graph-Based Orchestration**: Moving beyond simple linear "chain" prompts into non-linear directed graphs, allowing for branching logic, parallel execution, and cycles/loops.
- **Deterministic vs. Probabilistic Separation**: Strict boundaries are kept between tasks requiring AI reasoning (policy compliance) and tasks requiring mathematical certainty (duplicate detection). The LLM is purposely *not* used for duplicate checking to prevent hallucinations.
- **Structured Outputs**: Extensive use of Pydantic models paired with LangChain's `.with_structured_output()` ensures the LLM always returns strongly-typed data (JSON) rather than free-form text, making the pipeline perfectly stable.
- **Durable Human-in-the-Loop**: Using a Checkpointer (`SqliteSaver`), the state of the graph is frozen and serialized to a database when human input is required. The main process can be completely shut down, and the graph can be resumed days later without losing context.
- **Context Injection**: Dynamically providing the LLM with localized context (RAG-style), specifically pulling in an employee's CSV spending history to help the LLM define what "normal" spending looks like for that specific person.

---

## Tech Stack

- **Python**: Core programming language.
- **LangGraph & LangChain**: Framework for building stateful, multi-actor applications and managing LLM interactions.
- **Google Gemini API (`gemini-3.8-flash` / `1.5-flash`)**: The multimodal LLM powering the vision extraction and complex reasoning.
- **SQLite**: Local database used for both the past-receipts index (duplicate checking) and LangGraph checkpoint persistence.
- **Pydantic**: Data validation and strict schema enforcement for LLM outputs.
- **Pillow & Imagehash**: Image processing for generating perceptual hashes to catch cropped or re-photographed receipt duplicates.

---

## Getting Started

### 1. Setup Environment
Ensure you have Python installed, then set up your environment:
```bash
python -m venv venv
.\venv\Scripts\activate
pip install langchain langgraph langgraph-checkpoint-sqlite langchain-google-genai google-generativeai imagehash Pillow pydantic python-dotenv
```

### 2. Configure API Key
Create a `.env` file in the root directory and add your Gemini API Key:
```env
GEMINI_API_KEY="your_api_key_here"
```

### 3. Initialize the Database
Seed the SQLite database with the synthetic employee spending history and past receipts:
```bash
python data/seed_db.py
```

### 4. Run the Tests
Execute the main graph orchestrator, which processes the real receipt images located in the `receipts/` directory:
```bash
python main.py
```

### 5. Be the Human-in-the-Loop
If any expenses are flagged as ambiguous or require escalation, the graph will pause. Run the review script to view the AI's reasoning and provide your final verdict:
```bash
python human_review.py
```