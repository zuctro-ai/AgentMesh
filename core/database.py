import time
from typing import Dict, List, Optional
from core.models import (
    AgentTask, WorkerInfo, TaskStatus, AgentStatus, TelemetryMetrics,
    ChargebackRecord, AgentPluginBinding
)


class DatabaseStore:
    def __init__(self):
        self.tasks: Dict[str, AgentTask] = {}
        self.workers: Dict[str, WorkerInfo] = {}
        self.chargeback_records: List[ChargebackRecord] = []
        self.plugin_bindings: Dict[str, AgentPluginBinding] = {}
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

    def save_worker(self, worker: WorkerInfo):
        self.workers[worker.worker_id] = worker

    def get_worker(self, worker_id: str) -> Optional[WorkerInfo]:
        return self.workers.get(worker_id)

    def get_all_workers(self) -> List[WorkerInfo]:
        return list(self.workers.values())

    def update_worker_status(self, worker_id: str, status: AgentStatus, current_task_id: Optional[str] = None):
        if worker_id in self.workers:
            worker = self.workers[worker_id]
            worker.status = status
            worker.current_task_id = current_task_id
            worker.last_heartbeat = time.time()

    def update_worker_heartbeat(self, worker_id: str):
        if worker_id in self.workers:
            self.workers[worker_id].last_heartbeat = time.time()

    def record_token_usage(self, prompt_tokens: int, completion_tokens: int, cost_usd: float):
        total = prompt_tokens + completion_tokens
        self.system_metrics["total_tokens_burned"] += total
        self.system_metrics["total_cost_usd"] += cost_usd

    def save_chargeback(self, record: ChargebackRecord):
        self.chargeback_records.append(record)

    def record_chargeback(self, tenant_id: str, cost_center: str, prompt_tokens: int, completion_tokens: int, cost_usd: float):
        rec = ChargebackRecord(
            task_id=f"proxy_{int(time.time()*1000)}",
            tenant_id=tenant_id,
            cost_center=cost_center,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            timestamp=time.time()
        )
        self.save_chargeback(rec)


    def get_chargeback_report(self, start_time: float = 0.0) -> dict:
        filtered = [r for r in self.chargeback_records if r.timestamp >= start_time]
        tenants_map: Dict[str, dict] = {}

        for rec in filtered:
            key = f"{rec.tenant_id}:{rec.cost_center}"
            if key not in tenants_map:
                tenants_map[key] = {
                    "tenant_id": rec.tenant_id,
                    "cost_center": rec.cost_center,
                    "total_tasks": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_cost_usd": 0.0,
                    "breakdown_by_model": {
                        "gpt-4o": 0.0
                    }
                }
            item = tenants_map[key]
            item["total_tasks"] += 1
            item["prompt_tokens"] += rec.prompt_tokens
            item["completion_tokens"] += rec.completion_tokens
            item["total_cost_usd"] = round(item["total_cost_usd"] + rec.cost_usd, 6)
            item["breakdown_by_model"]["gpt-4o"] = round(item["breakdown_by_model"]["gpt-4o"] + rec.cost_usd, 6)

        return {
            "period_start": int(start_time),
            "tenants": list(tenants_map.values())
        }

    def save_plugin_binding(self, binding: AgentPluginBinding):
        self.plugin_bindings[binding.name] = binding

    def get_plugin_binding(self, name: str) -> Optional[AgentPluginBinding]:
        return self.plugin_bindings.get(name)

    def list_plugin_bindings(self) -> List[AgentPluginBinding]:
        return list(self.plugin_bindings.values())

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
