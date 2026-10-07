"""Agent 2: Allocation & Inventory Optimization Agent (Deterministic Solver).

Responsibilities:
1. Receives validated order and items.
2. Queries warehouse inventory state across facilities.
3. Filters out any facility marked in MAINTENANCE.
4. Solves allocation deterministically to minimize split shipments and stockouts.
5. Produces an exact, auditable AllocationPlan.
"""

from typing import Dict, List
from ..guardrails.security_policy import WAREHOUSE_FACILITY_STATUS
from ..models import AllocationLine, AllocationPlan, InventoryItem, WorkflowStatus
from ..state import OrchestratorState
from ..telemetry import AgentTelemetry

# Simulated multi-facility warehouse stock catalog
MOCK_WAREHOUSE_CATALOG: Dict[str, List[InventoryItem]] = {
    "WH-EAST-01": [
        InventoryItem(sku="SKU-CHIP-900", warehouse_id="WH-EAST-01", available_qty=500, unit_cost_usd=120.0),
        InventoryItem(sku="SKU-SENS-410", warehouse_id="WH-EAST-01", available_qty=200, unit_cost_usd=45.0),
        InventoryItem(sku="SKU-VALV-102", warehouse_id="WH-EAST-01", available_qty=50, unit_cost_usd=210.0),
    ],
    "WH-WEST-02": [
        InventoryItem(sku="SKU-CHIP-900", warehouse_id="WH-WEST-02", available_qty=800, unit_cost_usd=118.0),
        InventoryItem(sku="SKU-SENS-410", warehouse_id="WH-WEST-02", available_qty=1000, unit_cost_usd=42.0),
        InventoryItem(sku="SKU-VALV-102", warehouse_id="WH-WEST-02", available_qty=300, unit_cost_usd=205.0),
    ],
    "WH-CENTRAL-03": [
        # Facility is offline in WAREHOUSE_FACILITY_STATUS
        InventoryItem(sku="SKU-CHIP-900", warehouse_id="WH-CENTRAL-03", available_qty=2000, unit_cost_usd=110.0),
    ],
}


def allocation_agent_node(state: OrchestratorState) -> dict:
    """Agent 2 Node: Deterministically allocates stock from eligible warehouses."""
    order = state["order"]
    lines: List[AllocationLine] = []
    total_cost = 0.0
    total_requested = sum(i.quantity for i in order.items)
    total_allocated = 0

    # Operational filter: Only consider warehouses that are ONLINE
    eligible_warehouses = [
        wh_id for wh_id, status in WAREHOUSE_FACILITY_STATUS.items() if status == "ONLINE"
    ]

    for item in order.items:
        allocated_for_item = 0
        assigned_warehouse = "NONE"
        best_unit_cost = 0.0

        # Scan eligible warehouses for stock
        for wh_id in eligible_warehouses:
            wh_stocks = MOCK_WAREHOUSE_CATALOG.get(wh_id, [])
            match = next((s for s in wh_stocks if s.sku == item.sku), None)

            if match and match.available_qty >= item.quantity:
                # Preferred single warehouse fulfill
                assigned_warehouse = wh_id
                allocated_for_item = item.quantity
                best_unit_cost = match.unit_cost_usd
                break
            elif match and match.available_qty > allocated_for_item:
                # Partial candidate
                assigned_warehouse = wh_id
                allocated_for_item = min(match.available_qty, item.quantity)
                best_unit_cost = match.unit_cost_usd

        line_cost = allocated_for_item * best_unit_cost
        total_cost += line_cost
        total_allocated += allocated_for_item

        lines.append(
            AllocationLine(
                sku=item.sku,
                allocated_qty=allocated_for_item,
                requested_qty=item.quantity,
                warehouse_id=assigned_warehouse,
                unit_cost_usd=best_unit_cost,
                line_total_usd=line_cost,
                is_fulfilled=(allocated_for_item == item.quantity),
            )
        )

    fulfillment_rate = (total_allocated / total_requested * 100.0) if total_requested > 0 else 0.0
    is_fully_fulfilled = all(line.is_fulfilled for line in lines)
    lead_time_days = 2 if is_fully_fulfilled else 5

    plan = AllocationPlan(
        order_id=order.order_id,
        lines=lines,
        total_cost_usd=round(total_cost, 2),
        fulfillment_rate_pct=round(fulfillment_rate, 1),
        is_fully_fulfilled=is_fully_fulfilled,
        estimated_lead_time_days=lead_time_days,
    )

    log_entry = AgentTelemetry.emit_event(
        agent_name="AGENT-2: ALLOCATION_SOLVER",
        action="OPTIMIZE_STOCK_ALLOCATION",
        status="ALLOCATED",
        message=(
            f"Fulfillment Rate: {plan.fulfillment_rate_pct}% ({total_allocated}/{total_requested} units). "
            f"Total Inventory Cost: ${plan.total_cost_usd:,.2f}. Lead time: {lead_time_days} days."
        ),
        metadata={
            "order_id": order.order_id,
            "fulfillment_rate": plan.fulfillment_rate_pct,
            "total_cost_usd": plan.total_cost_usd,
            "is_fully_fulfilled": is_fully_fulfilled,
        },
    )

    return {
        "allocation_plan": plan,
        "workflow_status": WorkflowStatus.ALLOCATED.value,
        "telemetry_trail": [log_entry],
    }
