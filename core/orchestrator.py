import asyncio
import time
from typing import Optional, List, Dict, Any
from core.models import (
    AgentTask, TaskStatus, WorkerInfo, AgentStatus, HITLDecision,
    ChargebackRecord, TaskEvent
)
from core.database import db
from core.plugins import plugin_engine
from core.telemetry import otel_emitter


class TaskOrchestrator:
    def __init__(self):
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.event_listeners: Dict[str, List[asyncio.Queue]] = {}
        self.is_running: bool = False

    def subscribe_events(self, task_id: str) -> asyncio.Queue:
        q = asyncio.Queue()
        if task_id not in self.event_listeners:
            self.event_listeners[task_id] = []
        self.event_listeners[task_id].append(q)
        return q

    def unsubscribe_events(self, task_id: str, q: asyncio.Queue):
        if task_id in self.event_listeners and q in self.event_listeners[task_id]:
            self.event_listeners[task_id].remove(q)
            if not self.event_listeners[task_id]:
                del self.event_listeners[task_id]

    async def _emit_event(self, task: AgentTask, prev_status: Optional[TaskStatus] = None):
        event = TaskEvent(
            task_id=task.task_id,
            status=task.status.value,
            tenant_id=task.tenant_id,
            prompt_tokens=task.telemetry.prompt_tokens,
            completion_tokens=task.telemetry.completion_tokens,
            cost_usd=task.telemetry.total_cost_usd,
            payload_json=task.payload.model_dump_json()
        )
        if prev_status and prev_status != task.status:
            otel_emitter.emit_task_span(task, prev_status, task.status)

        if task.task_id in self.event_listeners:
            for q in self.event_listeners[task.task_id]:
                await q.put(event)

    async def submit_task(self, task: AgentTask, plugin_binding_name: Optional[str] = None) -> tuple[bool, str]:
        binding = None
        if plugin_binding_name:
            binding = db.get_plugin_binding(plugin_binding_name)

        prev_status = task.status
        res = plugin_engine.run_pipeline(task, binding)

        if res.modified_task:
            task = res.modified_task

        if not res.allowed:
            task.status = TaskStatus.FAILED
            task.error_message = res.rejection_reason or "Governance plugin check failed"
            db.save_task(task)
            await self._emit_event(task, prev_status)
            return False, task.error_message

        if res.requires_hitl:
            task.status = TaskStatus.WAITING_HITL
            task.hitl_trigger_tool = res.hitl_trigger_tool
            db.save_task(task)
            await self._emit_event(task, prev_status)
            return True, f"Task paused for HITL approval on tool: {res.hitl_trigger_tool}"

        task.status = TaskStatus.QUEUED
        db.save_task(task)
        await self.queue.put((-task.priority, task.created_at, task.task_id))
        await self._emit_event(task, prev_status)
        return True, "Task enqueued successfully"

    async def get_next_task_for_worker(self, agent_type: str, worker_id: Optional[str] = None) -> Optional[AgentTask]:
        if self.queue.empty():
            return None

        temp_items = []
        target_task: Optional[AgentTask] = None

        while not self.queue.empty():
            priority, created_at, task_id = await self.queue.get()
            task = db.get_task(task_id)

            if task and task.status == TaskStatus.QUEUED:
                if task.agent_type == agent_type or task.agent_type == "general_worker":
                    target_task = task
                    break
                else:
                    temp_items.append((priority, created_at, task_id))

        for item in temp_items:
            await self.queue.put(item)

        if target_task:
            prev_status = target_task.status
            target_task.status = TaskStatus.RUNNING
            target_task.assigned_worker_id = worker_id
            target_task.updated_at = time.time()
            db.save_task(target_task)

            if worker_id:
                db.update_worker_status(worker_id, AgentStatus.BUSY, target_task.task_id)

            await self._emit_event(target_task, prev_status)

        return target_task

    async def pause_task_for_hitl(self, task_id: str, tool_name: str) -> AgentTask:
        task = db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        prev_status = task.status
        task.status = TaskStatus.WAITING_HITL
        task.hitl_trigger_tool = tool_name
        task.updated_at = time.time()
        db.save_task(task)

        # Dispatch real-time Slack/Teams notification bot card
        from core.hitl_bot import hitl_bot
        hitl_bot.dispatch_hitl_notification(
            task_id=task.task_id,
            tool_name=tool_name,
            instruction=task.payload.instruction,
            tenant_id=task.tenant_id
        )

        await self._emit_event(task, prev_status)
        return task


    async def resume_task_from_hitl(self, decision: HITLDecision) -> AgentTask:
        task = db.get_task(decision.task_id)
        if not task:
            raise ValueError(f"Task {decision.task_id} not found")

        if task.status != TaskStatus.WAITING_HITL:
            raise ValueError(f"Task {decision.task_id} is not in WAITING_HITL status (current status: {task.status.value})")

        prev_status = task.status
        dec_upper = decision.decision.upper()

        if dec_upper == "APPROVED":
            task.status = TaskStatus.QUEUED
            task.updated_at = time.time()
            db.save_task(task)
            await self.queue.put((-task.priority, time.time(), task.task_id))
        elif dec_upper == "REJECTED":
            task.status = TaskStatus.FAILED
            task.error_message = f"HITL Rejected by {decision.operator_id}: {decision.reason or 'No reason provided'}"
            task.updated_at = time.time()
            db.save_task(task)
            db.system_metrics["total_tasks_failed"] += 1
        else:
            raise ValueError(f"Invalid HITL decision: {decision.decision}")

        await self._emit_event(task, prev_status)
        return task

    async def process_task_result(self, task_id: str, status: TaskStatus, result: Optional[Dict[str, Any]] = None,
                                  error_message: Optional[str] = None, prompt_tokens: int = 0,
                                  completion_tokens: int = 0, cost_usd: float = 0.0,
                                  worker_id: Optional[str] = None) -> AgentTask:
        task = db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        prev_status = task.status

        # Check post-result budget overrun
        new_total_tokens = task.telemetry.total_tokens + prompt_tokens + completion_tokens
        new_total_cost = task.telemetry.total_cost_usd + cost_usd

        task.telemetry.prompt_tokens += prompt_tokens
        task.telemetry.completion_tokens += completion_tokens
        task.telemetry.total_tokens = new_total_tokens
        task.telemetry.total_cost_usd = new_total_cost
        db.record_token_usage(prompt_tokens, completion_tokens, cost_usd)

        budget_exceeded = (
            new_total_tokens > task.governance.max_token_budget or
            new_total_cost > task.governance.max_cost_usd
        )

        if budget_exceeded:
            task.status = TaskStatus.DLQ
            task.error_message = f"Budget limit exceeded (Tokens: {new_total_tokens}/{task.governance.max_token_budget}, Cost: ${new_total_cost:.4f}/${task.governance.max_cost_usd:.4f})"
            db.system_metrics["total_tasks_failed"] += 1
            task.updated_at = time.time()
            db.save_task(task)
            if worker_id:
                db.update_worker_status(worker_id, AgentStatus.IDLE, None)
            await self._emit_event(task, prev_status)
            return task

        if status == TaskStatus.COMPLETED:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            db.system_metrics["total_tasks_completed"] += 1

            # Save chargeback attribution record
            cb_record = ChargebackRecord(
                task_id=task.task_id,
                tenant_id=task.tenant_id,
                cost_center=task.cost_center,
                prompt_tokens=task.telemetry.prompt_tokens,
                completion_tokens=task.telemetry.completion_tokens,
                total_tokens=task.telemetry.total_tokens,
                cost_usd=task.telemetry.total_cost_usd,
                timestamp=time.time()
            )
            db.save_chargeback(cb_record)

            if worker_id:
                worker = db.get_worker(worker_id)
                if worker:
                    worker.tasks_completed += 1
                    worker.total_tokens_processed += task.telemetry.total_tokens
                db.update_worker_status(worker_id, AgentStatus.IDLE, None)

        elif status == TaskStatus.FAILED:
            if task.retries < task.max_retries:
                task.retries += 1
                task.status = TaskStatus.QUEUED
                task.error_message = f"Retry {task.retries}/{task.max_retries}: {error_message}"
                await self.queue.put((-task.priority, time.time(), task.task_id))
            else:
                task.status = TaskStatus.DLQ
                task.error_message = f"Max retries exceeded ({task.max_retries}). Error: {error_message}"
                db.system_metrics["total_tasks_failed"] += 1

            if worker_id:
                db.update_worker_status(worker_id, AgentStatus.IDLE, None)

        task.updated_at = time.time()
        db.save_task(task)
        await self._emit_event(task, prev_status)
        return task

    async def expire_stale_hitl_tasks(self, timeout_seconds: int = 86400):
        now = time.time()
        hitl_tasks = db.list_tasks(status=TaskStatus.WAITING_HITL, limit=500)
        for task in hitl_tasks:
            if (now - task.updated_at) > timeout_seconds:
                prev_status = task.status
                task.status = TaskStatus.FAILED
                task.error_message = "HITL approval timed out"
                task.updated_at = now
                db.save_task(task)
                db.system_metrics["total_tasks_failed"] += 1
                await self._emit_event(task, prev_status)

    async def expire_stale_workers(self, timeout_seconds: int = 300):
        now = time.time()
        for worker in db.get_all_workers():
            if (now - worker.last_heartbeat) > timeout_seconds:
                db.update_worker_status(worker.worker_id, AgentStatus.OFFLINE, None)


orchestrator = TaskOrchestrator()
