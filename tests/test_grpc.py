import json
import pytest
import grpc
import agentmesh.v2_pb2 as agentmesh_v2_pb2
import agentmesh.v2_pb2_grpc as agentmesh_v2_pb2_grpc
from grpc_service.server import create_grpc_server


@pytest.mark.asyncio
async def test_grpc_submit_poll_result_flow():
    server = create_grpc_server(port=50055)
    await server.start()

    try:
        async with grpc.aio.insecure_channel("localhost:50055") as channel:
            stub = agentmesh_v2_pb2_grpc.AgentMeshControlPlaneStub(channel)

            # 1. SubmitTask
            task_env = agentmesh_v2_pb2.TaskEnvelope(
                task_id="tsk_grpc_test_1",
                tenant_id="grpc_tenant",
                cost_center="cc_grpc",
                agent_type="grpc_worker",
                priority=4,
                instruction="Execute gRPC calculation",
                context_json=json.dumps({"input": 42})
            )
            sub_res = await stub.SubmitTask(agentmesh_v2_pb2.SubmitTaskRequest(task=task_env))
            assert sub_res.status == "QUEUED"
            assert sub_res.task_id == "tsk_grpc_test_1"

            # 2. PollTask
            poll_res = await stub.PollTask(agentmesh_v2_pb2.PollTaskRequest(worker_id="wrk_grpc_1", agent_type="grpc_worker"))
            assert poll_res.task.task_id == "tsk_grpc_test_1"
            assert poll_res.task.agent_type == "grpc_worker"

            # 3. SubmitResult
            sub_result_res = await stub.SubmitResult(agentmesh_v2_pb2.SubmitResultRequest(
                worker_id="wrk_grpc_1",
                task_id="tsk_grpc_test_1",
                status="COMPLETED",
                result_json=json.dumps({"output": 84}),
                prompt_tokens=100,
                completion_tokens=50,
                cost_usd=0.005
            ))
            assert sub_result_res.acknowledged is True
    finally:
        await server.stop(0)
