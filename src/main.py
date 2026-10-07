"""CLI demonstration runner for Enterprise Multi-Agent Orchestrator."""

import argparse
from typing import List
from langgraph.checkpoint.memory import MemorySaver
from src.models import (
    CustomerTier,
    HumanApprovalDecision,
    OrderItem,
    OrderRequest,
    WorkflowStatus,
)
from src.workflow import build_orchestrator_graph

# Sample Scenarios
SAMPLE_ORDERS = {
    "standard": OrderRequest(
        order_id="ORD-101",
        customer_id="CUST-GLOBAL-01",
        customer_tier=CustomerTier.STANDARD,
        raw_notes="Standard monthly replenishment for factory automation modules. Deliver next week.",
        items=[
            OrderItem(sku="SKU-CHIP-900", description="Microcontroller ASIC", quantity=100, unit_price_usd=150.0),
            OrderItem(sku="SKU-SENS-410", description="Optical Pressure Sensor", quantity=50, unit_price_usd=60.0),
        ],
        credit_limit_usd=50_000.0,
    ),
    "rush": OrderRequest(
        order_id="ORD-202-RUSH",
        customer_id="CUST-ENTERPRISE-88",
        customer_tier=CustomerTier.ENTERPRISE,
        raw_notes="URGENT: Main assembly line down in Bay 4. Require immediate dispatch and shock-proof freight ASAP!",
        items=[
            OrderItem(sku="SKU-VALV-102", description="High-Pressure Pneumatic Valve", quantity=25, unit_price_usd=250.0),
            OrderItem(sku="SKU-CHIP-900", description="Microcontroller ASIC", quantity=40, unit_price_usd=150.0),
        ],
        credit_limit_usd=100_000.0,
    ),
    "credit_violation": OrderRequest(
        order_id="ORD-999-OVERLIMIT",
        customer_id="CUST-RETAIL-05",
        customer_tier=CustomerTier.STANDARD,
        raw_notes="Bulk order request for upcoming quarter.",
        items=[
            OrderItem(sku="SKU-CHIP-900", description="Microcontroller ASIC", quantity=800, unit_price_usd=150.0),
        ],
        credit_limit_usd=20_000.0,  # Total is $120,000 > $20,000
    ),
    "sanctioned": OrderRequest(
        order_id="ORD-000-BLOCKED",
        customer_id="CUST-BLOCKED-99",
        customer_tier=CustomerTier.STANDARD,
        raw_notes="Standard procurement.",
        items=[
            OrderItem(sku="SKU-SENS-410", description="Sensor", quantity=10, unit_price_usd=60.0),
        ],
        credit_limit_usd=10_000.0,
    ),
}


def run_demo(scenario_name: str, use_checkpoint: bool = False, interactive: bool = False):
    order = SAMPLE_ORDERS.get(scenario_name, SAMPLE_ORDERS["standard"])

    print("=" * 80)
    print("      ENTERPRISE MULTI-AGENT ORDER FULFILLMENT ORCHESTRATOR")
    print("=" * 80)
    print(f"Scenario Selected : {scenario_name.upper()}")
    print(f"Order ID          : {order.order_id}")
    print(f"Customer          : {order.customer_id} ({order.customer_tier.value})")
    print(f"Notes             : \"{order.raw_notes}\"")
    print(f"Items Requested   : {sum(i.quantity for i in order.items)} units across {len(order.items)} SKUs\n")

    checkpointer = MemorySaver() if (use_checkpoint or interactive) else None
    interrupt_nodes = ["operations_approval"] if interactive else []

    app = build_orchestrator_graph(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes,
    )

    initial_state = {
        "order": order,
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

    config = {"configurable": {"thread_id": f"thread_{order.order_id}"}} if checkpointer else None

    # Step 1: Initial Invoke
    result = app.invoke(initial_state, config=config) if config else app.invoke(initial_state)

    # Interactive Human-in-the-Loop review
    if interactive and result.get("allocation_plan") and result.get("workflow_status") != WorkflowStatus.REJECTED.value:
        plan = result["allocation_plan"]
        print("\n[PAUSE: HUMAN-IN-THE-LOOP] Order paused before ERP commit.")
        print(f"Proposed Cost: ${plan.total_cost_usd:,.2f} | Fulfillment: {plan.fulfillment_rate_pct}%")

        choice = input("Operator Decision ([A]pprove / [R]eject): ").strip().upper()
        approval = HumanApprovalDecision(
            approver_id="ops_lead_live_session",
            approved=(choice != "R"),
            comments="Approved by operations controller" if choice != "R" else "Rejected due to margin limit",
            timestamp=AgentTelemetry.now_iso(),
        )

        # Resume execution
        resume_payload = {"human_approval": approval}
        result = app.invoke(resume_payload, config=config) if config else app.invoke({**result, **resume_payload})

    # Print Results
    print("\n--- 1. AUDIT TELEMETRY TRAIL (MONOTONIC APPEND-ONLY LOG) ---")
    for event in result["telemetry_trail"]:
        print(f"  • {event}")

    print("\n--- 2. TRIAGE ANALYSIS (AGENT 1: PROBABILISTIC) ---")
    print(f"  Inferred Priority : {result.get('inferred_priority')}")
    print(f"  Urgency Score     : {result.get('urgency_score'):.2f}")
    print(f"  Special Handling  : {result.get('detected_special_handling')}")
    print(f"  Summary           : {result.get('triage_summary')}")

    print("\n--- 3. POLICY GUARDRAIL DECISION (DETERMINISTIC GATE) ---")
    guardrail = result.get("guardrail_result")
    if guardrail:
        print(f"  Passed     : {guardrail.passed}")
        print(f"  Rule Name  : {guardrail.rule_name}")
        print(f"  Reason     : {guardrail.reason}")
        print(f"  Risk Score : {guardrail.risk_score}")

    plan = result.get("allocation_plan")
    if plan:
        print("\n--- 4. ALLOCATION & OPTIMIZATION PLAN (AGENT 2: DETERMINISTIC) ---")
        print(f"  Fulfillment Rate : {plan.fulfillment_rate_pct}%")
        print(f"  Total Cost       : ${plan.total_cost_usd:,.2f}")
        print(f"  Lead Time        : {plan.estimated_lead_time_days} days")
        print("  Allocated Lines  :")
        for line in plan.lines:
            status_flag = "FULFILLED" if line.is_fulfilled else "PARTIAL"
            print(
                f"    • SKU: {line.sku:14} | Qty: {line.allocated_qty}/{line.requested_qty} | "
                f"WH: {line.warehouse_id} | Total: ${line.line_total_usd:,.2f} [{status_flag}]"
            )

    receipt = result.get("erp_receipt")
    if receipt:
        print("\n--- 5. ERP DISPATCH RECEIPT (AGENT 3: SECURE API) ---")
        print(f"  Transaction ID   : {receipt.transaction_id}")
        print(f"  Target ERP       : {receipt.erp_system}")
        print(f"  Status           : {receipt.status}")
        print(f"  Dispatched Lines : {receipt.dispatched_items_count}")
        print(f"  Timestamp        : {receipt.timestamp}")

    print(f"\nFinal Workflow Status: {result.get('workflow_status')}")
    print("=" * 80)
    return result


def main():
    parser = argparse.ArgumentParser(description="Run Enterprise Multi-Agent Orchestrator.")
    parser.add_argument(
        "--scenario",
        type=str,
        default="rush",
        choices=["standard", "rush", "credit_violation", "sanctioned"],
        help="Select business order scenario to execute.",
    )
    parser.add_argument(
        "--checkpoint",
        action="store_true",
        help="Enable thread state persistence via checkpointer.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Pause for interactive Human-in-the-Loop review before dispatch.",
    )
    args = parser.parse_args()

    run_demo(args.scenario, use_checkpoint=args.checkpoint, interactive=args.interactive)


if __name__ == "__main__":
    main()
