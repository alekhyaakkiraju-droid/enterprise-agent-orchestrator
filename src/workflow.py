"""Workflow definition compiling Agent 1, Policy Gate, Agent 2, and Dispatcher via LangGraph."""

from typing import List, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from .state import OrchestratorState
from .agents.triage_agent import triage_agent_node
from .agents.policy_node import policy_gate_node, route_after_policy_gate
from .agents.allocation_agent import allocation_agent_node
from .agents.approval_agent import operations_approval_node, rejection_handler_node


def build_orchestrator_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    interrupt_before: Optional[List[str]] = None,
):
    """Compiles the collaborative multi-agent workflow graph.
    
    Architecture:
    START
      │
      ▼
    [Agent 1: Triage Agent] (Probabilistic NLP extraction)
      │
      ▼
    [Policy Gate Node] (Deterministic 'Can Do / Can't Do' rules)
      │
      ├── (Passed) ──> [Agent 2: Allocation Solver] ──> [Agent 3: Approval & ERP Dispatch] ──> END
      │
      └── (Failed) ──> [Rejection Handler] ──> END
    """
    workflow = StateGraph(OrchestratorState)

    # 1. Register Nodes
    workflow.add_node("triage_agent", triage_agent_node)
    workflow.add_node("policy_gate", policy_gate_node)
    workflow.add_node("allocation_agent", allocation_agent_node)
    workflow.add_node("operations_approval", operations_approval_node)
    workflow.add_node("rejection_handler", rejection_handler_node)

    # 2. Register Edges
    workflow.add_edge(START, "triage_agent")
    workflow.add_edge("triage_agent", "policy_gate")

    workflow.add_conditional_edges(
        "policy_gate",
        route_after_policy_gate,
        {
            "allocation_agent": "allocation_agent",
            "rejection_handler": "rejection_handler",
        },
    )

    workflow.add_edge("allocation_agent", "operations_approval")
    workflow.add_edge("operations_approval", END)
    workflow.add_edge("rejection_handler", END)

    # 3. Compile Graph
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before or [],
    )
