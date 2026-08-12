from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from core.models import AgentTask, TaskStatus, WorkerInfo, AgentStatus
from core.database import db
from core.orchestrator import orchestrator

app = FastAPI(
    title="AgentMesh Control Plane & Gateway API",
    description="Open-Source Multi-Agent Control Plane (AM-CP-v1.0 Standard)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def get_root():
    return {
        "name": "AgentMesh Control Plane Gateway",
        "specification": "AM-CP-v1.0",
        "status": "HEALTHY",
        "summary": db.get_system_summary()
    }

@app.post("/v1/tasks", status_code=status.HTTP_201_CREATED)
async def submit_task(task: AgentTask):
    success, message = await orchestrator.submit_task(task)
    if not success:
        raise HTTPException(status_code=422, detail=message)
    return {
        "status": "success",
        "task_id": task.task_id,
        "state": task.status,
        "message": message
    }

@app.get("/v1/tasks/{task_id}", response_model=AgentTask)
def get_task_details(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task

@app.get("/v1/tasks")
def list_tasks(status: Optional[TaskStatus] = None, limit: int = 50):
    return db.list_tasks(status=status, limit=limit)

@app.post("/v1/workers/poll")
async def poll_task_for_worker(worker_id: str, agent_type: str):
    db.update_worker_heartbeat(worker_id)
    task = await orchestrator.get_next_task_for_worker(agent_type)
    return {"task": task}

@app.post("/v1/workers/submit-result")
async def submit_task_result(task_id: str, status: TaskStatus, result: Optional[dict] = None, 
                             error_message: Optional[str] = None, prompt_tokens: int = 0, 
                             completion_tokens: int = 0, cost_usd: float = 0.0):
    task = await orchestrator.process_task_result(
        task_id=task_id,
        status=status,
        result=result,
        error_message=error_message,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd
    )
    return {"status": "success", "task": task}

@app.get("/v1/metrics/summary")
def get_metrics_summary():
    return db.get_system_summary()
