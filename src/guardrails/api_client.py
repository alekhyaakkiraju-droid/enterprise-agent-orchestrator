"""Secure API client wrapper with authentication, timeouts, retries, and telemetry."""

import functools
import time
import uuid
from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel
from ..telemetry import AgentTelemetry


class SecureAPIClient:
    """Wraps external ERP and warehouse API calls with guardrails and telemetry."""

    @staticmethod
    def call_enterprise_api(
        agent_id: str,
        role: str,
        endpoint_name: str,
        payload: BaseModel,
        mock_handler: Callable[[Dict[str, Any]], Dict[str, Any]],
        timeout_seconds: float = 3.0,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """Executes an API call under strict guardrails.
        
        Guardrail Enforcement:
        1. Role Authorization Check (RBAC).
        2. Input schema validation (via Pydantic payload).
        3. Timeout & retry handling.
        4. Structured audit telemetry logging.
        """
        start_time = time.time()
        correlation_id = str(uuid.uuid4())[:8]

        # 1. RBAC Check ('Can Do / Can't Do')
        allowed_roles = {"fulfillment_agent", "operations_admin", "erp_dispatcher"}
        if role not in allowed_roles:
            err_msg = f"Security Violation: Role '{role}' unauthorized for endpoint '{endpoint_name}'."
            AgentTelemetry.emit_event(
                agent_name=agent_id,
                action=f"API_CALL:{endpoint_name}",
                status="DENIED",
                message=err_msg,
                metadata={"correlation_id": correlation_id, "role": role},
            )
            raise PermissionError(err_msg)

        # 2. Serialize and validate payload
        data = payload.model_dump()

        # 3. Execution with Retries & Telemetry
        attempts = 0
        last_exception = None

        while attempts <= max_retries:
            attempts += 1
            try:
                # Forward timeout_seconds to dispatch handler
                try:
                    response = mock_handler(data, timeout=timeout_seconds)
                except TypeError:
                    response = mock_handler(data)
                duration_ms = round((time.time() - start_time) * 1000, 2)

                AgentTelemetry.emit_event(
                    agent_name=agent_id,
                    action=f"API_CALL:{endpoint_name}",
                    status="SUCCESS",
                    message=f"Dispatched {endpoint_name} successfully (status 200).",
                    metadata={
                        "correlation_id": correlation_id,
                        "duration_ms": duration_ms,
                        "attempts": attempts,
                    },
                )
                return response

            except Exception as exc:
                last_exception = exc
                if attempts <= max_retries:
                    time.sleep(0.05 * (2 ** (attempts - 1)))  # Exponential backoff

        duration_ms = round((time.time() - start_time) * 1000, 2)
        AgentTelemetry.emit_event(
            agent_name=agent_id,
            action=f"API_CALL:{endpoint_name}",
            status="FAILED",
            message=f"API call failed after {attempts} attempts: {str(last_exception)}",
            metadata={"correlation_id": correlation_id, "duration_ms": duration_ms},
        )
        raise RuntimeError(f"API '{endpoint_name}' invocation failed: {str(last_exception)}")
