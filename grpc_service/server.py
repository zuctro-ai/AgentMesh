import json
import asyncio
import grpc
import agentmesh.v2_pb2 as agentmesh_v2_pb2
import agentmesh.v2_pb2_grpc as agentmesh_v2_pb2_grpc


from core.models import AgentTask, TaskPayload, TaskStatus, HITLDecision
from core.database import db
from core.orchestrator import orchestrator


class AgentMeshControlPlaneServicer(agentmesh_v2_pb2_grpc.AgentMeshControlPlaneServicer):

    async def SubmitTask(self, request, context):
        env = request.task
        ctx = json.loads(env.context_json) if env.context_json else {}
        task = AgentTask(
            task_id=env.task_id or None,
            parent_task_id=env.parent_task_id or None,
            tenant_id=env.tenant_id or "default_tenant",
            cost_center=env.cost_center or "default",
            agent_type=env.agent_type or "general_worker",
            priority=env.priority or 1,
            payload=TaskPayload(instruction=env.instruction, context=ctx)
        )

        success, msg = await orchestrator.submit_task(task)
        return agentmesh_v2_pb2.SubmitTaskResponse(
            task_id=task.task_id,
            status=task.status.value,
            message=msg
        )

    async def PollTask(self, request, context):
        task = await orchestrator.get_next_task_for_worker(request.agent_type, worker_id=request.worker_id)
        if not task:
            return agentmesh_v2_pb2.PollTaskResponse()

        env = agentmesh_v2_pb2.TaskEnvelope(
            task_id=task.task_id,
            parent_task_id=task.parent_task_id or "",
            tenant_id=task.tenant_id,
            cost_center=task.cost_center,
            agent_type=task.agent_type,
            priority=task.priority,
            status=task.status.value,
            instruction=task.payload.instruction,
            context_json=json.dumps(task.payload.context),
            created_at=int(task.created_at)
        )
        return agentmesh_v2_pb2.PollTaskResponse(task=env)

    async def SubmitResult(self, request, context):
        res_json = json.loads(request.result_json) if request.result_json else {}
        status_val = request.status
        if status_val in TaskStatus.__members__:
            status_enum = TaskStatus[status_val]
        else:
            status_enum = TaskStatus(status_val)

        await orchestrator.process_task_result(
            task_id=request.task_id,
            status=status_enum,
            result=res_json,
            error_message=request.error_message,
            prompt_tokens=request.prompt_tokens,
            completion_tokens=request.completion_tokens,
            cost_usd=request.cost_usd,
            worker_id=request.worker_id
        )
        return agentmesh_v2_pb2.SubmitResultResponse(acknowledged=True)

    async def SubmitHITLDecision(self, request, context):
        decision = HITLDecision(
            task_id=request.task_id,
            decision=request.decision,
            operator_id=request.operator_id,
            reason=request.reason
        )
        updated_task = await orchestrator.resume_task_from_hitl(decision)
        return agentmesh_v2_pb2.HITLDecisionResponse(
            success=True,
            new_status=updated_task.status.value
        )

    async def StreamTaskEvents(self, request, context):
        q = orchestrator.subscribe_events(request.task_id)
        try:
            while True:
                event = await q.get()
                yield agentmesh_v2_pb2.TaskEvent(
                    task_id=event.task_id,
                    status=event.status,
                    prompt_tokens=event.prompt_tokens,
                    completion_tokens=event.completion_tokens,
                    cost_usd=event.cost_usd,
                    payload_json=event.payload_json or ""
                )
                if event.status in ("COMPLETED", "FAILED", "DEAD_LETTER_QUEUE", "CANCELLED"):
                    break
        finally:
            orchestrator.unsubscribe_events(request.task_id, q)


def create_grpc_server(port: int = 50051):
    server = grpc.aio.server()
    agentmesh_v2_pb2_grpc.add_AgentMeshControlPlaneServicer_to_server(AgentMeshControlPlaneServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    return server
