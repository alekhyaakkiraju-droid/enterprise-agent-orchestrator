"""Deterministic security policies, access control (RBAC), and guardrail rules."""

from typing import Dict, List, Tuple
from ..models import OrderRequest, GuardrailDecision, WorkflowStatus
from ..telemetry import AgentTelemetry

# Simulated enterprise blacklist / suspended customer list
SUSPENDED_CUSTOMER_ACCOUNTS = {"CUST-BLOCKED-99", "CUST-SANCTIONED-00"}

# Active warehouse facility operational status
WAREHOUSE_FACILITY_STATUS = {
    "WH-EAST-01": "ONLINE",
    "WH-WEST-02": "ONLINE",
    "WH-CENTRAL-03": "MAINTENANCE",  # Offline for re-tooling
}


class PolicyGuardrailEngine:
    """Deterministic policy gatekeeper enforcing 'Can Do / Can't Do' rules."""

    @staticmethod
    def evaluate_order(order: OrderRequest) -> Tuple[bool, GuardrailDecision]:
        """Evaluates deterministic business and security rules.
        
        Zero LLM hallucination: Evaluated via pure boolean logic.
        """
        # 1. Check Customer Account Health
        if order.customer_id in SUSPENDED_CUSTOMER_ACCOUNTS:
            decision = GuardrailDecision(
                passed=False,
                rule_name="ACCOUNT_STATUS_CHECK",
                reason=f"Customer account '{order.customer_id}' is suspended or flagged for compliance review.",
                risk_score=1.0,
            )
            return False, decision

        # 2. Check Order Line Items Validity
        if not order.items:
            decision = GuardrailDecision(
                passed=False,
                rule_name="EMPTY_ORDER_CHECK",
                reason="Order payload contains zero line items.",
                risk_score=0.9,
            )
            return False, decision

        # 3. Check Financial Credit Limit ('Can Do / Can't Do')
        total_order_value = sum(item.quantity * item.unit_price_usd for item in order.items)
        if total_order_value > order.credit_limit_usd:
            decision = GuardrailDecision(
                passed=False,
                rule_name="CREDIT_LIMIT_EXCEEDED",
                reason=(
                    f"Total order value (${total_order_value:,.2f}) exceeds customer approved "
                    f"credit limit (${order.credit_limit_usd:,.2f})."
                ),
                risk_score=0.85,
            )
            return False, decision

        # 4. Check Individual Item Quantities (Sanity Check)
        for item in order.items:
            if item.quantity > 50_000:
                decision = GuardrailDecision(
                    passed=False,
                    rule_name="UNUSUAL_VOLUME_ANOMALY",
                    reason=f"SKU '{item.sku}' quantity ({item.quantity}) exceeds single-order threshold (50,000).",
                    risk_score=0.75,
                )
                return False, decision

        # All deterministic rules passed
        decision = GuardrailDecision(
            passed=True,
            rule_name="ALL_POLICIES_SATISFIED",
            reason=f"Order passed compliance, credit (${total_order_value:,.2f} <= ${order.credit_limit_usd:,.2f}), and volume checks.",
            risk_score=0.05,
        )
        return True, decision
