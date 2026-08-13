import json
import asyncio
from fastapi import FastAPI, HTTPException, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from typing import Optional, List
from core.models import (
    AgentTask, TaskStatus, WorkerInfo, AgentStatus, HITLDecision,
    MCPToolCallRequest, AgentPluginBinding
)
from core.database import db
from core.orchestrator import orchestrator
from core.plugins import plugin_engine
from core.mcp_gateway import mcp_gateway

app = FastAPI(
    title="Zuctro AgentMesh Control Plane & Gateway API",
    description="Enterprise Multi-Agent Control Plane (AM-CP-v2.5 Standard)",
    version="2.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, Response

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def get_ui():
    return FileResponse("static/index.html")


@app.get("/api/info")
def get_api_info():
    return {
        "name": "Zuctro AgentMesh Enterprise Control Plane Gateway",
        "specification": "AM-CP-v2.5",
        "version": "2.5.0-ENTERPRISE-STANDARD",
        "status": "HEALTHY",
        "summary": db.get_system_summary()
    }



@app.post("/v1/tasks", status_code=status.HTTP_201_CREATED)
async def submit_task(task: AgentTask, plugin_binding: Optional[str] = None):
    success, message = await orchestrator.submit_task(task, plugin_binding_name=plugin_binding)
    if not success:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)
    return {
        "status": "success",
        "task_id": task.task_id,
        "state": task.status,
        "hitl_trigger_tool": task.hitl_trigger_tool,
        "message": message
    }


@app.get("/v1/tasks/{task_id}", response_model=AgentTask)
def get_task_details(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")
    return task


@app.get("/v1/tasks")
def list_tasks(status: Optional[TaskStatus] = None, limit: int = 50):
    return db.list_tasks(status=status, limit=limit)


@app.get("/v1/tasks/{task_id}/stream")
async def stream_task_events(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")

    q = orchestrator.subscribe_events(task_id)

    async def event_generator():
        try:
            # First send current task state
            first_event_data = json.dumps({
                "task_id": task.task_id,
                "status": task.status.value,
                "tenant_id": task.tenant_id,
                "prompt_tokens": task.telemetry.prompt_tokens,
                "completion_tokens": task.telemetry.completion_tokens,
                "cost_usd": task.telemetry.total_cost_usd,
                "timestamp": task.created_at
            })
            yield f"data: {first_event_data}\n\n"

            terminal_statuses = {"COMPLETED", "FAILED", "DEAD_LETTER_QUEUE", "CANCELLED"}
            if task.status.value in terminal_statuses:
                return

            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    event_data = event.model_dump_json()
                    yield f"data: {event_data}\n\n"

                    if event.status in terminal_statuses:
                        break
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            orchestrator.unsubscribe_events(task_id, q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/v1/hitl/{task_id}/decision")
async def submit_hitl_decision(task_id: str, decision_payload: dict):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")

    if task.status != TaskStatus.WAITING_HITL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task {task_id} is not in WAITING_HITL status (current status: {task.status.value})"
        )

    decision = HITLDecision(
        task_id=task_id,
        decision=decision_payload.get("decision", "APPROVED"),
        operator_id=decision_payload.get("operator_id", "admin"),
        reason=decision_payload.get("reason")
    )

    updated_task = await orchestrator.resume_task_from_hitl(decision)
    return {
        "status": "success",
        "task_id": updated_task.task_id,
        "new_state": updated_task.status,
        "message": f"HITL decision '{decision.decision}' recorded"
    }


@app.post("/v1/workers/poll")
async def poll_task_for_worker(worker_id: str, agent_type: str):
    worker = db.get_worker(worker_id)
    if not worker:
        worker = WorkerInfo(worker_id=worker_id, agent_type=agent_type)
        db.register_worker(worker)
    else:
        db.update_worker_heartbeat(worker_id)

    task = await orchestrator.get_next_task_for_worker(agent_type, worker_id=worker_id)
    return {"task": task}


@app.post("/v1/workers/submit-result")
async def submit_task_result(task_id: str, status: TaskStatus, result: Optional[dict] = None,
                             error_message: Optional[str] = None, prompt_tokens: int = 0,
                             completion_tokens: int = 0, cost_usd: float = 0.0,
                             worker_id: Optional[str] = None):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found")

    updated_task = await orchestrator.process_task_result(
        task_id=task_id,
        status=status,
        result=result,
        error_message=error_message,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        worker_id=worker_id
    )
    return {"status": "success", "task": updated_task}


@app.get("/v1/workers")
def list_workers():
    return db.get_all_workers()


@app.get("/v1/mcp/tools")
def list_mcp_tools(tenant_id: str = "default_tenant", user_role: Optional[str] = None):
    return mcp_gateway.list_tools(tenant_id=tenant_id, user_role=user_role)


@app.post("/v1/mcp/tools/call")
def call_mcp_tool(request: MCPToolCallRequest):
    return mcp_gateway.call_tool(request)


@app.post("/v1/mcp/servers")
def register_mcp_server(payload: dict):
    name = payload.get("name")
    url = payload.get("endpoint_url")
    token = payload.get("auth_token")
    if not name or not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'name' or 'endpoint_url'")
    mcp_gateway.register_mcp_server(name, url, token)
    return {"status": "success", "message": f"MCP server '{name}' registered"}


@app.post("/v1/mcp/servers/{server_name}/sync")
def sync_mcp_server_tools(server_name: str):
    tools = mcp_gateway.sync_remote_mcp_tools(server_name)
    return {"status": "success", "discovered_tools": tools}


@app.post("/v1/chat/completions")
async def chat_completions_proxy(payload: dict, request: Request):
    """Governed OpenAI-compatible LLM Gateway Proxy Endpoint.
    Intercepts chat completions, enforces PII sanitization and prompt injection checks,
    computes usage, and attributes financial chargeback.
    """
    messages = payload.get("messages", [])
    model = payload.get("model", "gpt-4o")
    tenant_id = request.headers.get("x-tenant-id", "default_tenant")
    cost_center = request.headers.get("x-cost-center", "default")

    sanitized_messages = []
    total_prompt_tokens = 0

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            if GovernanceInterceptor.check_prompt_injection(content):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="OWASP Prompt Injection detected in message content"
                )
            clean_content, _ = GovernanceInterceptor.sanitize_text(content)
            sanitized_messages.append({"role": msg.get("role"), "content": clean_content})
            total_prompt_tokens += len(clean_content.split())
        else:
            sanitized_messages.append(msg)

    completion_content = f"Governed response from AgentMesh LLM Proxy [{model}]: Processed query with full governance checks."
    completion_tokens = len(completion_content.split())
    cost_usd = (total_prompt_tokens * 0.000005) + (completion_tokens * 0.000015)

    db.record_chargeback(
        tenant_id=tenant_id,
        cost_center=cost_center,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd
    )

    return {
        "id": "chatcmpl-agentmesh-proxy",
        "object": "chat.completion",
        "created": 1786563200,
        "model": model,
        "governance": {
            "pii_redacted": True,
            "prompt_injection_checked": True,
            "cost_usd": cost_usd
        },
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": completion_content
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_prompt_tokens + completion_tokens
        }
    }




@app.get("/v1/metrics/summary")
def get_metrics_summary():
    return db.get_system_summary()


@app.get("/v1/metrics/chargeback")
def get_chargeback_report(start_time: float = 0.0):
    return db.get_chargeback_report(start_time=start_time)


@app.post("/v1/plugins/bindings")
async def create_plugin_binding(request: Request):
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    yaml_str = body.decode("utf-8")

    try:
        binding = plugin_engine.load_binding(yaml_str)
        db.save_plugin_binding(binding)
        return {"status": "success", "binding": binding}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/v1/plugins/bindings")
def list_plugin_bindings():
    return db.list_plugin_bindings()


@app.get("/metrics")
def prometheus_metrics():
    summary = db.get_system_summary()
    queued_tasks = summary["queued_tasks"]
    active_workers = summary["active_workers"]
    completed_tasks = summary["completed_tasks"]
    failed_tasks = summary["failed_tasks"]

    metrics_text = f"""# HELP agentmesh_queued_tasks Number of tasks currently queued awaiting worker polling (KEDA Trigger)
# TYPE agentmesh_queued_tasks gauge
agentmesh_queued_tasks {queued_tasks}

# HELP agentmesh_active_workers Number of active busy worker pods
# TYPE agentmesh_active_workers gauge
agentmesh_active_workers {active_workers}

# HELP agentmesh_completed_tasks Total completed tasks count
# TYPE agentmesh_completed_tasks counter
agentmesh_completed_tasks {completed_tasks}

# HELP agentmesh_failed_tasks Total failed tasks count
# TYPE agentmesh_failed_tasks counter
agentmesh_failed_tasks {failed_tasks}
"""
    return Response(content=metrics_text, media_type="text/plain")
