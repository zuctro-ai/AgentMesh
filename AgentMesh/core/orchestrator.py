import asyncio
import time
from typing import Optional, List, Dict, Any
from core.models import AgentTask, TaskStatus, WorkerInfo, AgentStatus
from core.database import db
from core.governance import GovernanceInterceptor


class TaskOrchestrator:
    def __init__(self):
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.is_running: bool = False

    async def submit_task(self, task: AgentTask) -> tuple[bool, str]:
        passed, msg = GovernanceInterceptor.validate_task_submission(task)
        if not passed:
            task.status = TaskStatus.FAILED
            task.error_message = msg
            db.save_task(task)
            return False, msg

        task.status = TaskStatus.QUEUED
        db.save_task(task)

        await self.queue.put((-task.priority, task.created_at, task.task_id))
        return True, "Task enqueued successfully"

    async def get_next_task_for_worker(self, agent_type: str) -> Optional[AgentTask]:
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
            target_task.status = TaskStatus.RUNNING
            target_task.updated_at = time.time()
            db.save_task(target_task)

        return target_task

    async def process_task_result(self, task_id: str, status: TaskStatus, result: Optional[Dict[str, Any]] = None, 
                                  error_message: Optional[str] = None, prompt_tokens: int = 0, 
                                  completion_tokens: int = 0, cost_usd: float = 0.0) -> AgentTask:
        task = db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.telemetry.prompt_tokens += prompt_tokens
        task.telemetry.completion_tokens += completion_tokens
        task.telemetry.total_tokens = task.telemetry.prompt_tokens + task.telemetry.completion_tokens
        task.telemetry.total_cost_usd += cost_usd

        db.record_token_usage(prompt_tokens, completion_tokens, cost_usd)

        if status == TaskStatus.COMPLETED:
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
            db.system_metrics["total_tasks_completed"] += 1

        elif status == TaskStatus.FAILED:
            if task.retries < task.max_retries:
                task.retries += 1
                task.status = TaskStatus.QUEUED
                task.error_message = f"Retry {task.retries}/{task.max_retries}: {error_message}"
                await self.queue.put((-task.priority, time.time(), task.task_id))
            else:
                task.status = TaskStatus.DLQ
                task.error_message = f"Max retries exceeded. Error: {error_message}"
                db.system_metrics["total_tasks_failed"] += 1

        task.updated_at = time.time()
        db.save_task(task)
        return task


orchestrator = TaskOrchestrator()
