"""Deterministic Policy Gate Node.

Enforces zero-tolerance security boundaries between Agent 1 and Agent 2.
"""

from typing import Literal
from ..guardrails.security_policy import PolicyGuardrailEngine
from ..models import WorkflowStatus
from ..state import OrchestratorState
from ..telemetry import AgentTelemetry


def policy_gate_node(state: OrchestratorState) -> dict:
    """Evaluates deterministic business rules to approve or reject order progression."""
    order = state["order"]
    is_approved, decision = PolicyGuardrailEngine.evaluate_order(order)

    status_tag = "APPROVED" if is_approved else "REJECTED"
    log_entry = AgentTelemetry.emit_event(
        agent_name="POLICY_GATE",
        action="EVALUATE_COMPLIANCE",
        status=status_tag,
        message=f"Rule '{decision.rule_name}': {decision.reason}",
        metadata={"passed": is_approved, "risk_score": decision.risk_score},
    )

    return {
        "guardrail_result": decision,
        "is_policy_approved": is_approved,
        "workflow_status": WorkflowStatus.POLICY_APPROVED.value if is_approved else WorkflowStatus.REJECTED.value,
        "telemetry_trail": [log_entry],
    }


def route_after_policy_gate(state: OrchestratorState) -> Literal["allocation_agent", "rejection_handler"]:
    """Conditional router based on policy gate evaluation."""
    if state.get("is_policy_approved", False):
        return "allocation_agent"
    return "rejection_handler"
