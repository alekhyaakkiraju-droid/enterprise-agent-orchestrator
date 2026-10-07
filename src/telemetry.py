"""Structured audit telemetry and observability module."""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("agent.orchestrator.telemetry")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class AgentTelemetry:
    """Helper for producing structured, auditable telemetry events across agent steps."""

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def emit_event(
        cls,
        agent_name: str,
        action: str,
        status: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Logs structured JSON event and returns formatted trail entry for LangGraph state."""
        timestamp = cls.now_iso()
        meta = metadata or {}
        event = {
            "timestamp": timestamp,
            "agent": agent_name,
            "action": action,
            "status": status,
            "message": message,
            "metadata": meta,
        }

        # Log to standard logging system
        logger.info(json.dumps(event))

        # Format concise entry for the state's telemetry_trail
        meta_str = f" | meta={json.dumps(meta)}" if meta else ""
        return f"[{timestamp}] [{agent_name}:{action}] [{status}] {message}{meta_str}"
