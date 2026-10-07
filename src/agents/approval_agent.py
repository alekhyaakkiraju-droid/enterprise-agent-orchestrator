"""Agent 3: Operational Risk Evaluator & Secure ERP Dispatcher.

Responsibilities:
1. Evaluates financial and operational risk (Human-in-the-Loop criteria).
2. Flags orders requiring human sign-off (e.g. high-value orders, partial fulfillment).
3. If approved, executes secure enterprise API call to dispatch order to ERP (SAP / WMS).
4. Emits structured telemetry and transaction receipt.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from ..guardrails.api_client import SecureAPIClient
from ..models import (
    ERPDispatchReceipt,
    HumanApprovalDecision,
    OrderPriority,
    WorkflowStatus,
)
from ..state import OrchestratorState
from ..telemetry import AgentTelemetry


def mock_erp_s4hana_order_creation(payload: Dict[str, Any], timeout: float = 3.0) -> Dict[str, Any]:
    """Simulates an enterprise ERP (e.g. SAP S/4HANA) sales order creation endpoint."""
    return {
        "status": "CREATED",
        "erp_sales_order_number": f"SO-{uuid.uuid4().hex[:8].upper()}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lines_booked": len(payload.get("lines", [])),
    }


def operations_approval_node(state: OrchestratorState) -> dict:
    """Agent 3 Node: Assesses risk thresholds and dispatches approved orders to ERP."""
    plan = state.get("allocation_plan")
    order = state["order"]
    existing_approval = state.get("human_approval")
    priority = state.get("inferred_priority", OrderPriority.STANDARD)

    if not plan:
        return {
            "workflow_status": WorkflowStatus.REJECTED.value,
            "telemetry_trail": [
                AgentTelemetry.emit_event(
                    agent_name="AGENT-3: ERP_DISPATCHER",
                    action="EVALUATE_DISPATCH",
                    status="SKIPPED",
                    message="No allocation plan found to dispatch.",
                )
            ],
        }

    # High-risk criteria: Value > $50,000 OR Partial Fulfillment OR Critical Urgency
    is_high_value = plan.total_cost_usd >= 50_000.0
    is_partial = not plan.is_fully_fulfilled
    is_critical = priority == OrderPriority.CRITICAL

    # Case A: Awaiting Human Sign-off
    if (is_high_value or is_partial or is_critical) and not existing_approval:
        reasons = []
        if is_high_value:
            reasons.append(f"High value (${plan.total_cost_usd:,.2f} >= $50,000)")
        if is_partial:
            reasons.append(f"Partial fulfillment ({plan.fulfillment_rate_pct}%)")
        if is_critical:
            reasons.append("Critical rush priority")

        reason_str = ", ".join(reasons)
        log_entry = AgentTelemetry.emit_event(
            agent_name="AGENT-3: ERP_DISPATCHER",
            action="RISK_EVALUATION",
            status="FLAGGED_FOR_HUMAN",
            message=f"Order held for human sign-off: {reason_str}.",
            metadata={"reasons": reasons, "cost_usd": plan.total_cost_usd},
        )
        return {
            "requires_human_approval": True,
            "workflow_status": WorkflowStatus.AWAITING_APPROVAL.value,
            "telemetry_trail": [log_entry],
        }

    # Case B: Human Rejected
    if existing_approval and not existing_approval.approved:
        log_entry = AgentTelemetry.emit_event(
            agent_name="AGENT-3: ERP_DISPATCHER",
            action="HUMAN_SIGN_OFF",
            status="REJECTED",
            message=f"Human operator '{existing_approval.approver_id}' rejected order: {existing_approval.comments}",
            metadata={"approver": existing_approval.approver_id},
        )
        return {
            "workflow_status": WorkflowStatus.REJECTED.value,
            "requires_human_approval": False,
            "telemetry_trail": [log_entry],
        }

    # Case C: Approved (Auto-approved or Human-approved) -> Call Secure ERP API
    try:
        erp_response = SecureAPIClient.call_enterprise_api(
            agent_id="AGENT-3: ERP_DISPATCHER",
            role="erp_dispatcher",
            endpoint_name="/api/v1/erp/sales-orders",
            payload=plan,
            mock_handler=mock_erp_s4hana_order_creation,
        )

        receipt = ERPDispatchReceipt(
            transaction_id=erp_response["erp_sales_order_number"],
            erp_system="SAP_S4HANA_GLOBAL",
            status=erp_response["status"],
            dispatched_items_count=erp_response["lines_booked"],
            total_value_usd=plan.total_cost_usd,
            timestamp=erp_response["timestamp"],
        )

        approval_summary = (
            f"Human signed-off by {existing_approval.approver_id}"
            if existing_approval
            else "Auto-approved within standard risk limits"
        )

        log_entry = AgentTelemetry.emit_event(
            agent_name="AGENT-3: ERP_DISPATCHER",
            action="COMMIT_ORDER",
            status="DISPATCHED",
            message=f"Dispatched to ERP ({receipt.erp_system}) as {receipt.transaction_id}. {approval_summary}.",
            metadata={"transaction_id": receipt.transaction_id, "cost_usd": receipt.total_value_usd},
        )

        return {
            "erp_receipt": receipt,
            "requires_human_approval": False,
            "workflow_status": WorkflowStatus.DISPATCHED.value,
            "telemetry_trail": [log_entry],
        }

    except Exception as exc:
        log_entry = AgentTelemetry.emit_event(
            agent_name="AGENT-3: ERP_DISPATCHER",
            action="COMMIT_ORDER",
            status="FAILED",
            message=f"Dispatch failed: {str(exc)}",
        )
        return {
            "workflow_status": WorkflowStatus.REJECTED.value,
            "telemetry_trail": [log_entry],
        }


def rejection_handler_node(state: OrchestratorState) -> dict:
    """Safe fallback node executed when guardrails reject an order."""
    guardrail = state.get("guardrail_result")
    reason = guardrail.reason if guardrail else "Security guardrail violation."

    log_entry = AgentTelemetry.emit_event(
        agent_name="WORKFLOW_REJECTION_HANDLER",
        action="HALT_ORDER",
        status="REJECTED",
        message=f"Order processing halted safely: {reason}",
    )

    return {
        "workflow_status": WorkflowStatus.REJECTED.value,
        "telemetry_trail": [log_entry],
    }
