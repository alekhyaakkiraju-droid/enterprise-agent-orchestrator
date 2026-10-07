# enterprise-agent-orchestrator

> **Multi-Agent Collaborative Order Fulfillment & Supply Allocation Orchestrator** built with **LangGraph**, **Pydantic**, and **Python**.

An enterprise-grade reference architecture demonstrating **Agent-to-Agent (A2A)** workflows, strict separation between **probabilistic reasoning** and **deterministic execution**, policy-based **security guardrails**, and **monotonic audit telemetry**.

---

## 1. Architectural Blueprint

```
                                [Customer Order Event / Request]
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ AGENT 1: Ingestion & Triage Agent (`triage_agent.py`)                                         │
│  • Probabilistic Natural Language Processing (NLP) of customer notes & delivery constraints.  │
│  • Infers operational urgency (CRITICAL, EXPEDITED, STANDARD) and special handling tags.       │
│  • Formulates structured operational summary for downstream processing.                       │
└───────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ DETERMINISTIC POLICY GUARDRAIL GATE (`security_policy.py`)                                    │
│  • Zero-hallucination security boundary ("Agent Can Do / Can't Do").                          │
│  • Credit limit threshold check: Blocks orders exceeding account credit lines.                │
│  • Account compliance & sanction list screening.                                              │
│  • Order volume and anomaly validation.                                                       │
└───────────────────────┬───────────────────────────────────────────────┬───────────────────────┘
                        │ Approved                                      │ Rejected
                        ▼                                               ▼
┌───────────────────────────────────────────────┐     ┌─────────────────────────────────────────┐
│ AGENT 2: Inventory & Allocation Solver        │     │ SAFE REJECTION HANDLER                  │
│ (`allocation_agent.py`)                       │     │  • Emits warning telemetry.             │
│  • Deterministic inventory solver.            │     │  • Halts execution gracefully.          │
│  • Filters facility health (skips offline WH).│     └─────────────────────────────────────────┘
│  • Minimizes split shipments & stockouts.     │
│  • Generates verified AllocationPlan.         │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ AGENT 3: Operational Risk Evaluator & Secure ERP Dispatcher (`approval_agent.py`)             │
│  • Evaluates financial risk: Orders > $50,000 or partial fills require Human-in-the-Loop.     │
│  • Dispatches approved orders to enterprise ERP (SAP S/4HANA mock) via secure API client.     │
│  • Returns verified ERPDispatchReceipt.                                                       │
└───────────────────────┬───────────────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ MONOTONIC AUDIT TELEMETRY TRAIL (`telemetry.py`)                                              │
│  • Immutable, append-only event stream using LangGraph reducers (`Annotated[list, add]`).     │
│  • Structured JSON logs with timestamps, correlation IDs, agent IDs, and execution latency.   │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Engineering Principles

### A. Deterministic vs. Probabilistic Separation
* **Probabilistic Steps (Agent 1):** Ingests free-form delivery notes, interprets priority nuances, and classifies special handling tags (e.g. *Temperature-Controlled Freight*).
* **Deterministic Steps (Guardrails & Agent 2):** Solves inventory allocation, verifies credit lines, checks warehouse status, and calculates exact line totals. Mathematical guarantees protect against hallucinations and unauthorized dispatches.

### B. Security Guardrails & API Protection
* **"Can Do / Can't Do" Boundaries:** Autonomous agents can triage, read inventory, and draft allocation plans. They **cannot** dispatch orders to suspended accounts, override financial credit limits, or push unapproved high-risk orders to ERP.
* **Role-Based Access Control (RBAC):** API calls are enforced with authorized roles (`erp_dispatcher`).
* **Schema Contracts:** All data handoffs use strictly typed Pydantic models.

### C. Observability & Monotonic Telemetry
* Uses LangGraph's `Annotated[List[str], operator.add]` state reducer to ensure that each agent appends to the audit trail without the ability to mutate or overwrite previous events.

---

## 3. Directory Layout

```
enterprise-agent-orchestrator/
├── pyproject.toml              # Build & dependency metadata
├── requirements.txt            # Python dependencies
├── README.md                   # System documentation
├── src/
│   ├── __init__.py
│   ├── models.py               # Pydantic schemas (OrderRequest, AllocationPlan, Receipts)
│   ├── state.py                # LangGraph OrchestratorState with telemetry reducer
│   ├── telemetry.py            # Structured JSON logger & audit telemetry emitter
│   ├── workflow.py             # LangGraph StateGraph compiling all agents & gates
│   ├── main.py                 # CLI demonstration runner
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── security_policy.py  # Deterministic business rules & compliance checks
│   │   └── api_client.py       # Secure API client with retries, timeouts, and RBAC
│   └── agents/
│       ├── __init__.py
│       ├── triage_agent.py     # Agent 1: NLP Ingestion & Triage
│       ├── policy_node.py      # Policy Gate Node
│       ├── allocation_agent.py # Agent 2: Inventory Allocation Solver
│       └── approval_agent.py   # Agent 3: Risk Evaluation & ERP Dispatcher
└── tests/
    ├── __init__.py
    └── test_workflow.py        # Pytest test suite covering full lifecycle
```

---

## 4. Quickstart

### 1. Set Up Virtual Environment

```bash
cd ~/Projects/enterprise-agent-orchestrator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Workflow Demo

**Scenario 1: Rush Order (Priority triage + ERP dispatch):**
```bash
python -m src.main --scenario rush
```

**Scenario 2: Guardrail Rejection (Credit limit violation):**
```bash
python -m src.main --scenario credit_violation
```

**Scenario 3: With State Persistence (Checkpointer):**
```bash
python -m src.main --scenario standard --checkpoint
```

**Scenario 4: Interactive Human-in-the-Loop Review:**
```bash
python -m src.main --scenario rush --interactive
```

### 3. Run Automated Tests

```bash
pytest -v
```
