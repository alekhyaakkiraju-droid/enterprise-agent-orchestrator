"""Comprehensive unit and integration test suite for Enterprise Multi-Agent Orchestrator."""

import pytest
from langgraph.checkpoint.memory import MemorySaver
from src.guardrails.api_client import SecureAPIClient
from src.models import (
    CustomerTier,
    HumanApprovalDecision,
    OrderItem,
    OrderPriority,
    OrderRequest,
    WorkflowStatus,
)
from src.workflow import build_orchestrator_graph


@pytest.fixture
def standard_order():
    return OrderRequest(
        order_id="TEST-ORD-01",
        customer_id="CUST-ACME-CORP",
        customer_tier=CustomerTier.STANDARD,
        raw_notes="Standard restocking order for sensors and valves.",
        items=[
            OrderItem(sku="SKU-CHIP-900", description="Chip", quantity=50, unit_price_usd=120.0),
            OrderItem(sku="SKU-SENS-410", description="Sensor", quantity=30, unit_price_usd=45.0),
        ],
        credit_limit_usd=50_000.0,
    )


@pytest.fixture
def overlimit_order():
    return OrderRequest(
        order_id="TEST-ORD-OVERLIMIT",
        customer_id="CUST-SMB-12",
        customer_tier=CustomerTier.STANDARD,
        raw_notes="Large bulk expansion.",
        items=[
            OrderItem(sku="SKU-CHIP-900", description="Chip", quantity=1000, unit_price_usd=150.0),
        ],
        credit_limit_usd=10_000.0,  # $150,000 exceeds $10,000
    )


def test_standard_order_happy_path(standard_order):
    """Tests full pipeline: Triage -> Policy Approved -> Allocated -> ERP Dispatched."""
    app = build_orchestrator_graph()

    state = {
        "order": standard_order,
        "triage_summary": "",
        "inferred_priority": None,
        "urgency_score": 0.0,
        "detected_special_handling": [],
        "guardrail_result": None,
        "is_policy_approved": False,
        "allocation_plan": None,
        "human_approval": None,
        "requires_human_approval": False,
        "erp_receipt": None,
        "workflow_status": WorkflowStatus.RECEIVED.value,
        "telemetry_trail": [],
    }

    result = app.invoke(state)

    # Assertions
    assert result["is_policy_approved"] is True
    assert result["allocation_plan"] is not None
    assert result["allocation_plan"].is_fully_fulfilled is True
    assert result["erp_receipt"] is not None
    assert result["workflow_status"] == WorkflowStatus.DISPATCHED.value

    # Verify append-only telemetry logged events from every agent
    telemetry = " ".join(result["telemetry_trail"])
    assert "AGENT-1: TRIAGE" in telemetry
    assert "POLICY_GATE" in telemetry
    assert "AGENT-2: ALLOCATION_SOLVER" in telemetry
    assert "AGENT-3: ERP_DISPATCHER" in telemetry


def test_guardrail_credit_limit_violation(overlimit_order):
    """Tests deterministic security gate: blocks order exceeding credit limit."""
    app = build_orchestrator_graph()

    state = {
        "order": overlimit_order,
        "triage_summary": "",
        "inferred_priority": None,
        "urgency_score": 0.0,
        "detected_special_handling": [],
        "guardrail_result": None,
        "is_policy_approved": False,
        "allocation_plan": None,
        "human_approval": None,
        "requires_human_approval": False,
        "erp_receipt": None,
        "workflow_status": WorkflowStatus.RECEIVED.value,
        "telemetry_trail": [],
    }

    result = app.invoke(state)

    # Assert policy rejected before reaching Agent 2
    assert result["is_policy_approved"] is False
    assert result["guardrail_result"].rule_name == "CREDIT_LIMIT_EXCEEDED"
    assert result["allocation_plan"] is None
    assert result["erp_receipt"] is None
    assert result["workflow_status"] == WorkflowStatus.REJECTED.value

    telemetry = " ".join(result["telemetry_trail"])
    assert "WORKFLOW_REJECTION_HANDLER" in telemetry


def test_human_in_the_loop_approval(standard_order):
    """Tests high-risk human approval override."""
    app = build_orchestrator_graph()

    human_signoff = HumanApprovalDecision(
        approver_id="vp_operations_dan",
        approved=True,
        comments="Approved rush bypass for strategic tier account.",
        timestamp="2026-10-07T12:00:00Z",
    )

    state = {
        "order": standard_order,
        "triage_summary": "",
        "inferred_priority": None,
        "urgency_score": 0.0,
        "detected_special_handling": [],
        "guardrail_result": None,
        "is_policy_approved": False,
        "allocation_plan": None,
        "human_approval": human_signoff,
        "requires_human_approval": False,
        "erp_receipt": None,
        "workflow_status": WorkflowStatus.RECEIVED.value,
        "telemetry_trail": [],
    }

    result = app.invoke(state)
    assert result["workflow_status"] == WorkflowStatus.DISPATCHED.value
    assert any("vp_operations_dan" in log for log in result["telemetry_trail"])


def test_checkpointer_thread_isolation(standard_order, overlimit_order):
    """Tests LangGraph state persistence and thread isolation."""
    checkpointer = MemorySaver()
    app = build_orchestrator_graph(checkpointer=checkpointer)

    config_1 = {"configurable": {"thread_id": "thread_order_1"}}
    config_2 = {"configurable": {"thread_id": "thread_order_2"}}

    state_1 = {
        "order": standard_order,
        "triage_summary": "",
        "inferred_priority": None,
        "urgency_score": 0.0,
        "detected_special_handling": [],
        "guardrail_result": None,
        "is_policy_approved": False,
        "allocation_plan": None,
        "human_approval": None,
        "requires_human_approval": False,
        "erp_receipt": None,
        "workflow_status": WorkflowStatus.RECEIVED.value,
        "telemetry_trail": [],
    }

    state_2 = {
        "order": overlimit_order,
        "triage_summary": "",
        "inferred_priority": None,
        "urgency_score": 0.0,
        "detected_special_handling": [],
        "guardrail_result": None,
        "is_policy_approved": False,
        "allocation_plan": None,
        "human_approval": None,
        "requires_human_approval": False,
        "erp_receipt": None,
        "workflow_status": WorkflowStatus.RECEIVED.value,
        "telemetry_trail": [],
    }

    res_1 = app.invoke(state_1, config=config_1)
    res_2 = app.invoke(state_2, config=config_2)

    assert res_1["is_policy_approved"] is True
    assert res_2["is_policy_approved"] is False

    # Checkpoint retrieval
    saved_1 = app.get_state(config_1)
    saved_2 = app.get_state(config_2)

    assert saved_1.values["workflow_status"] == WorkflowStatus.DISPATCHED.value
    assert saved_2.values["workflow_status"] == WorkflowStatus.REJECTED.value


def test_api_security_rbac():
    """Tests RBAC guardrail on SecureAPIClient."""
    from pydantic import BaseModel

    class DummyPayload(BaseModel):
        test: str = "ok"

    # Authorized role succeeds
    res = SecureAPIClient.call_enterprise_api(
        agent_id="TEST-AGENT",
        role="erp_dispatcher",
        endpoint_name="/test",
        payload=DummyPayload(),
        mock_handler=lambda p: {"status": "SUCCESS"},
    )
    assert res["status"] == "SUCCESS"

    # Unauthorized role raises PermissionError
    with pytest.raises(PermissionError):
        SecureAPIClient.call_enterprise_api(
            agent_id="TEST-AGENT",
            role="unauthorized_guest",
            endpoint_name="/test",
            payload=DummyPayload(),
            mock_handler=lambda p: {"status": "SUCCESS"},
        )
