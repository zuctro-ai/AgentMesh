import asyncio
import pytest
from hypothesis import given, settings, strategies as st
from core.models import (
    AgentTask, TaskPayload, GovernancePolicy, TaskStatus, HITLDecision,
    WorkerInfo, AgentStatus
)
from core.database import DatabaseStore, db
from core.orchestrator import TaskOrchestrator


@pytest.mark.asyncio
async def test_priority_queue_ordering():
    orch = TaskOrchestrator()
    
    t1 = AgentTask(priority=1, payload=TaskPayload(instruction="Low priority"))
    t2 = AgentTask(priority=5, payload=TaskPayload(instruction="High priority"))
    t3 = AgentTask(priority=3, payload=TaskPayload(instruction="Medium priority"))

    for t in [t1, t2, t3]:
        await orch.submit_task(t)

    n1 = await orch.get_next_task_for_worker("general_worker")
    n2 = await orch.get_next_task_for_worker("general_worker")
    n3 = await orch.get_next_task_for_worker("general_worker")

    assert n1.task_id == t2.task_id  # priority 5
    assert n2.task_id == t3.task_id  # priority 3
    assert n3.task_id == t1.task_id  # priority 1



@pytest.mark.asyncio
async def test_hitl_pause_and_roundtrip():
    orch = TaskOrchestrator()
    task = AgentTask(
        governance=GovernancePolicy(require_hitl_for_tools=["git_push_production"]),
        payload=TaskPayload(instruction="Please git_push_production to main")
    )
    
    success, msg = await orch.submit_task(task)
    assert success is True
    assert task.status == TaskStatus.WAITING_HITL
    assert task.hitl_trigger_tool == "git_push_production"

    # Property 7: HITL Pause Prevents Worker Dequeue
    polled = await orch.get_next_task_for_worker("general_worker")
    assert polled is None

    # Property 8: HITL Round-Trip (Approve Restores Queueable State)
    decision = HITLDecision(task_id=task.task_id, decision="APPROVED", operator_id="admin_1")
    resumed = await orch.resume_task_from_hitl(decision)
    assert resumed.status == TaskStatus.QUEUED

    polled_after = await orch.get_next_task_for_worker("general_worker")
    assert polled_after is not None
    assert polled_after.task_id == task.task_id


@pytest.mark.asyncio
async def test_budget_exceeded_routes_to_dlq():
    orch = TaskOrchestrator()
    task = AgentTask(
        governance=GovernancePolicy(max_token_budget=100, max_cost_usd=0.10),
        payload=TaskPayload(instruction="Do work")
    )
    await orch.submit_task(task)

    # Submit result with prompt_tokens = 150 (exceeds budget 100)
    updated = await orch.process_task_result(
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        prompt_tokens=150,
        completion_tokens=0,
        cost_usd=0.05
    )

    assert updated.status == TaskStatus.DLQ
    assert "Budget limit exceeded" in updated.error_message


@pytest.mark.asyncio
async def test_retry_count_monotonically_increases_to_dlq():
    orch = TaskOrchestrator()
    task = AgentTask(
        max_retries=2,
        payload=TaskPayload(instruction="Failing task")
    )
    await orch.submit_task(task)

    # Fail 1
    t1 = await orch.process_task_result(task.task_id, TaskStatus.FAILED, error_message="Err 1")
    assert t1.retries == 1
    assert t1.status == TaskStatus.QUEUED

    # Fail 2
    t2 = await orch.process_task_result(task.task_id, TaskStatus.FAILED, error_message="Err 2")
    assert t2.retries == 2
    assert t2.status == TaskStatus.QUEUED

    # Fail 3 (Exceeds max_retries = 2)
    t3 = await orch.process_task_result(task.task_id, TaskStatus.FAILED, error_message="Err 3")
    assert t3.status == TaskStatus.DLQ
    assert "Max retries exceeded" in t3.error_message


@pytest.mark.asyncio
async def test_chargeback_attribution_consistency():
    orch = TaskOrchestrator()
    task = AgentTask(
        tenant_id="org_fintech",
        cost_center="cc_payments",
        payload=TaskPayload(instruction="Process payment")
    )
    await orch.submit_task(task)

    completed = await orch.process_task_result(
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        result={"status": "ok"},
        prompt_tokens=500,
        completion_tokens=200,
        cost_usd=0.015
    )

    assert completed.status == TaskStatus.COMPLETED
    report = db.get_chargeback_report(start_time=0.0)

    found = False
    for tenant in report["tenants"]:
        if tenant["tenant_id"] == "org_fintech" and tenant["cost_center"] == "cc_payments":
            found = True
            assert tenant["prompt_tokens"] >= 500
            assert tenant["completion_tokens"] >= 200
            assert tenant["total_cost_usd"] >= 0.015

    assert found is True
