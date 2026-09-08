import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, AsyncGenerator
from sqlmodel import Session, select

from backend.db import engine, Step, AuditLog
from backend.security import redact_secrets

logger = logging.getLogger("forge.logger")


class EventBroker:
    """
    Central event broker for real-time step streaming and audit logging.
    Enforces secret redaction at the single logging chokepoint and supports
    resumable SSE connections via Last-Event-ID.
    """

    def __init__(self):
        # run_id -> list of asyncio.Queue for active SSE subscribers
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        if run_id not in self._subscribers:
            self._subscribers[run_id] = []
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[run_id].append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue):
        if run_id in self._subscribers and q in self._subscribers[run_id]:
            self._subscribers[run_id].remove(q)
            if not self._subscribers[run_id]:
                del self._subscribers[run_id]

    async def log_step(
        self,
        run_id: str,
        step_index: int,
        action_type: str,
        tool_name: Optional[str] = None,
        tool_input: Optional[Any] = None,
        tool_output: Optional[Any] = None,
        status: str = "ok",
        provider_used: Optional[str] = None,
    ) -> Step:
        """
        Redacts secrets, writes step to SQLite, and broadcasts to active SSE subscribers.
        """
        # Redact secrets
        safe_input = redact_secrets(tool_input)
        safe_output = redact_secrets(tool_output)
        
        # Serialize tool_input if it is a dict
        input_str = json.dumps(safe_input) if isinstance(safe_input, (dict, list)) else (str(safe_input) if safe_input is not None else None)
        output_str = str(safe_output) if safe_output is not None else None

        # Persist to SQLite
        step = Step(
            run_id=run_id,
            step_index=step_index,
            action_type=action_type,
            tool_name=tool_name,
            tool_input=input_str,
            tool_output=output_str,
            status=status,
            provider_used=provider_used,
            timestamp=datetime.now(timezone.utc),
        )

        with Session(engine) as db_session:
            db_session.add(step)
            db_session.commit()
            db_session.refresh(step)

        # Broadcast SSE event
        payload = {
            "id": step.id,
            "run_id": run_id,
            "step_index": step_index,
            "action_type": action_type,
            "tool_name": tool_name,
            "tool_input": input_str,
            "tool_output": output_str,
            "status": status,
            "provider_used": provider_used,
            "timestamp": step.timestamp.isoformat(),
        }

        if run_id in self._subscribers:
            for q in list(self._subscribers[run_id]):
                try:
                    await q.put(payload)
                except Exception as e:
                    logger.error(f"Error queueing SSE event: {e}")

        return step

    def log_audit(
        self,
        event_type: str,
        actor_ip: Optional[str] = None,
        run_id: Optional[str] = None,
        details: Optional[Any] = None,
        status: str = "success",
    ) -> AuditLog:
        """
        Redacts sensitive tokens and persists security audit log entry to SQLite.
        """
        safe_details = redact_secrets(details)
        details_str = json.dumps(safe_details) if isinstance(safe_details, (dict, list)) else (str(safe_details) if safe_details is not None else None)

        audit_entry = AuditLog(
            event_type=event_type,
            actor_ip=actor_ip,
            run_id=run_id,
            details=details_str,
            status=status,
            timestamp=datetime.now(timezone.utc),
        )

        with Session(engine) as db_session:
            db_session.add(audit_entry)
            db_session.commit()
            db_session.refresh(audit_entry)

        return audit_entry

    async def stream_run_events(
        self, run_id: str, last_event_id: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """
        Yields Server-Sent Events with Last-Event-ID resume support.
        """
        # 1. Replay missed historical events if client provided Last-Event-ID
        with Session(engine) as db_session:
            query = select(Step).where(Step.run_id == run_id)
            if last_event_id is not None:
                query = query.where(Step.id > last_event_id)
            query = query.order_by(Step.id.asc())
            past_steps = db_session.exec(query).all()

            for step in past_steps:
                payload = {
                    "id": step.id,
                    "run_id": step.run_id,
                    "step_index": step.step_index,
                    "action_type": step.action_type,
                    "tool_name": step.tool_name,
                    "tool_input": step.tool_input,
                    "tool_output": step.tool_output,
                    "status": step.status,
                    "provider_used": step.provider_used,
                    "timestamp": step.timestamp.isoformat(),
                }
                yield f"id: {step.id}\nevent: step\ndata: {json.dumps(payload)}\n\n"

        # 2. Subscribe to live events
        q = self.subscribe(run_id)
        try:
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=20.0)
                    step_id = payload.get("id", "")
                    yield f"id: {step_id}\nevent: step\ndata: {json.dumps(payload)}\n\n"
                    if payload.get("action_type") in ["finish", "error", "stopped", "stuck"]:
                        break
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    yield ": ping\n\n"
        finally:
            self.unsubscribe(run_id, q)


event_broker = EventBroker()
