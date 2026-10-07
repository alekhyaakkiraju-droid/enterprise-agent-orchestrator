"""Shared multi-agent state with append-only audit telemetry."""

from typing import Annotated, List, Optional
import operator
from typing_extensions import TypedDict
from .models import (
    OrderRequest,
    OrderPriority,
    GuardrailDecision,
    AllocationPlan,
    HumanApprovalDecision,
    ERPDispatchReceipt,
)


def _bounded_telemetry_append(prev: Optional[List[str]], new: Optional[List[str]]) -> List[str]:
    """Append telemetry events while bounding history to the most recent 100 entries."""
    combined = (prev or []) + (new or [])
    return combined[-100:]


class OrchestratorState(TypedDict):
    """Shared state dictionary exchanged across agents and gates in the workflow."""

    # 1. Input Trigger Payload
    order: OrderRequest

    # 2. Agent 1 (Probabilistic Ingestion & Triage Agent)
    triage_summary: str
    inferred_priority: OrderPriority
    urgency_score: float  # 0.0 to 1.0
    detected_special_handling: List[str]

    # 3. Deterministic Policy Guardrail Gate
    guardrail_result: Optional[GuardrailDecision]
    is_policy_approved: bool

    # 4. Agent 2 (Deterministic Inventory & Allocation Optimizer Agent)
    allocation_plan: Optional[AllocationPlan]

    # 5. Human-in-the-Loop Review Node (if risk or value threshold exceeded)
    human_approval: Optional[HumanApprovalDecision]
    requires_human_approval: bool

    # 6. Agent 3 / Dispatcher Node (Secure ERP Integration)
    erp_receipt: Optional[ERPDispatchReceipt]

    # 7. Workflow Lifecycle State
    workflow_status: str

    # 8. Monotonic Audit Telemetry (Bounded reducer across all agent handoffs)
    telemetry_trail: Annotated[List[str], _bounded_telemetry_append]
