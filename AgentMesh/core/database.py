import time
from typing import Dict, List, Optional
from core.models import AgentTask, WorkerInfo, TaskStatus, AgentStatus, TelemetryMetrics


class DatabaseStore:
    def __init__(self):
        self.tasks: Dict[str, AgentTask] = {}
        self.workers: Dict[str, WorkerInfo] = {}
        self.system_metrics = {
            "total_tasks_processed": 0,
            "total_tasks_completed": 0,
            "total_tasks_failed": 0,
            "total_tokens_burned": 0,
            "total_cost_usd": 0.0,
            "system_start_time": time.time()
        }

    def save_task(self, task: AgentTask):
        task.updated_at = time.time()
        self.tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        return self.tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None, limit: int = 100) -> List[AgentTask]:
        all_tasks = list(self.tasks.values())
        if status:
            all_tasks = [t for t in all_tasks if t.status == status]
        return sorted(all_tasks, key=lambda x: x.created_at, reverse=True)[:limit]

    def register_worker(self, worker: WorkerInfo):
        self.workers[worker.worker_id] = worker

    def record_token_usage(self, prompt_tokens: int, completion_tokens: int, cost_usd: float):
        total = prompt_tokens + completion_tokens
        self.system_metrics["total_tokens_burned"] += total
        self.system_metrics["total_cost_usd"] += cost_usd

    def get_system_summary(self) -> dict:
        active_workers = len([w for w in self.workers.values() if w.status == AgentStatus.BUSY])
        idle_workers = len([w for w in self.workers.values() if w.status == AgentStatus.IDLE])
        queued_tasks = len([t for t in self.tasks.values() if t.status in (TaskStatus.PENDING, TaskStatus.QUEUED)])
        
        return {
            "total_tasks": len(self.tasks),
            "queued_tasks": queued_tasks,
            "active_workers": active_workers,
            "idle_workers": idle_workers,
            "total_workers": len(self.workers),
            "completed_tasks": self.system_metrics["total_tasks_completed"],
            "failed_tasks": self.system_metrics["total_tasks_failed"],
            "total_tokens_burned": self.system_metrics["total_tokens_burned"],
            "total_cost_usd": round(self.system_metrics["total_cost_usd"], 4),
            "uptime_seconds": int(time.time() - self.system_metrics["system_start_time"])
        }


db = DatabaseStore()
