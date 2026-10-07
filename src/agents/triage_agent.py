"""Agent 1: Ingestion & Triage Agent (Probabilistic Reasoning).

Responsibilities:
1. Ingests raw customer order requests, unstructured delivery notes, and account tier.
2. Performs natural-language understanding & semantic classification:
   - Infers operational urgency (CRITICAL, EXPEDITED, STANDARD).
   - Extracts delivery sensitivity and special handling tags (e.g., 'TEMPERATURE_CONTROLLED', 'DIRECT_FREIGHT').
3. Formulates structured operational summary for downstream agents.
4. Emits audit telemetry for tracing.
"""

from typing import List, Tuple
from ..models import OrderPriority, CustomerTier, WorkflowStatus
from ..state import OrchestratorState
from ..telemetry import AgentTelemetry


def analyze_unstructured_notes(notes: str, tier: CustomerTier) -> Tuple[OrderPriority, float, List[str]]:
    """Simulates NLP / LLM extraction of urgency, sentiment, and handling requirements."""
    notes_lower = notes.lower()
    special_handling: List[str] = []
    urgency_score = 0.3  # Base standard score

    # Semantic keyword detection (simulating prompt reasoning)
    is_rush = any(w in notes_lower for w in ["urgent", "asap", "emergency", "immediately", "critical", "rush"])
    is_line_down = any(w in notes_lower for w in ["line down", "halt", "production stop", "outage"])
    has_temp_sensitive = any(w in notes_lower for w in ["cold", "refrigerated", "temp", "thermal"])
    has_fragile = any(w in notes_lower for w in ["fragile", "delicate", "calibration"])

    if has_temp_sensitive:
        special_handling.append("TEMPERATURE_CONTROLLED_STORAGE")
    if has_fragile:
        special_handling.append("PRECISION_SHOCK_PROTECTION")

    if is_line_down:
        urgency_score = 0.95
        priority = OrderPriority.CRITICAL
        special_handling.append("PRIORITY_DOCK_EXPEDITE")
    elif is_rush or tier == CustomerTier.ENTERPRISE:
        urgency_score = 0.75
        priority = OrderPriority.EXPEDITED
    else:
        priority = OrderPriority.STANDARD

    return priority, urgency_score, special_handling


def triage_agent_node(state: OrchestratorState) -> dict:
    """Agent 1 Node: Triages incoming order and prepares structured context."""
    order = state["order"]
    
    inferred_priority, urgency_score, special_handling = analyze_unstructured_notes(
        order.raw_notes, order.customer_tier
    )

    triage_summary = (
        f"Order {order.order_id} classified as {inferred_priority.value} "
        f"(Urgency Score: {urgency_score:.2f}, Tier: {order.customer_tier.value}). "
        f"Items count: {len(order.items)}. "
        f"Special requirements: {special_handling if special_handling else 'Standard delivery'}."
    )

    log_entry = AgentTelemetry.emit_event(
        agent_name="AGENT-1: TRIAGE",
        action="ANALYZE_ORDER_INTENT",
        status="TRIAGED",
        message=triage_summary,
        metadata={
            "order_id": order.order_id,
            "inferred_priority": inferred_priority.value,
            "urgency_score": urgency_score,
            "special_handling": special_handling,
        },
    )

    return {
        "inferred_priority": inferred_priority,
        "urgency_score": urgency_score,
        "detected_special_handling": special_handling,
        "triage_summary": triage_summary,
        "workflow_status": WorkflowStatus.TRIAGED.value,
        "telemetry_trail": [log_entry],
    }
