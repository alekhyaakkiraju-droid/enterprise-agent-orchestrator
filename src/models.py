"""Domain models for enterprise order fulfillment and multi-agent coordination."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class OrderPriority(str, Enum):
    STANDARD = "STANDARD"
    EXPEDITED = "EXPEDITED"
    CRITICAL = "CRITICAL"


class CustomerTier(str, Enum):
    ENTERPRISE = "ENTERPRISE"
    PREMIUM = "PREMIUM"
    STANDARD = "STANDARD"


class WorkflowStatus(str, Enum):
    RECEIVED = "RECEIVED"
    TRIAGED = "TRIAGED"
    POLICY_APPROVED = "POLICY_APPROVED"
    ALLOCATED = "ALLOCATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    DISPATCHED = "DISPATCHED"
    REJECTED = "REJECTED"


class OrderItem(BaseModel):
    """Line item requested in a customer order."""
    sku: str
    description: str
    quantity: int = Field(..., gt=0, description="Quantity requested")
    unit_price_usd: float = Field(..., gt=0.0, description="Agreed unit price")


class OrderRequest(BaseModel):
    """Raw incoming customer order request with metadata and notes."""
    order_id: str
    customer_id: str
    customer_tier: CustomerTier = CustomerTier.STANDARD
    raw_notes: str = Field(default="", description="Unstructured customer instructions or rush request notes")
    items: List[OrderItem]
    requested_delivery_days: int = Field(default=7, ge=1)
    credit_limit_usd: float = Field(default=100_000.0, gt=0.0)


class InventoryItem(BaseModel):
    """Warehouse stock level for a SKU."""
    sku: str
    warehouse_id: str
    available_qty: int = Field(..., ge=0)
    reserved_qty: int = Field(default=0, ge=0)
    unit_cost_usd: float = Field(..., gt=0.0)


class AllocationLine(BaseModel):
    """Deterministic allocation decision per SKU."""
    sku: str
    allocated_qty: int
    requested_qty: int
    warehouse_id: str
    unit_cost_usd: float
    line_total_usd: float
    is_fulfilled: bool


class AllocationPlan(BaseModel):
    """Output produced by Agent 2 (Allocation & Optimization Agent)."""
    order_id: str
    lines: List[AllocationLine]
    total_cost_usd: float
    fulfillment_rate_pct: float
    is_fully_fulfilled: bool
    estimated_lead_time_days: int


class GuardrailDecision(BaseModel):
    """Result of deterministic policy guardrails."""
    passed: bool
    rule_name: str
    reason: str
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ERPDispatchReceipt(BaseModel):
    """Acknowledgment payload returned from simulated enterprise ERP dispatch."""
    transaction_id: str
    erp_system: str
    status: str
    dispatched_items_count: int
    total_value_usd: float
    timestamp: str


class HumanApprovalDecision(BaseModel):
    """Human-in-the-loop review decision for high-value or edge-case orders."""
    approver_id: str
    approved: bool
    comments: str
    timestamp: str
