import pytest
from fastapi.testclient import TestClient
from app import app
from core.models import TaskStatus

client = TestClient(app)


def test_root_endpoint():
    res = client.get("/api/info")
    assert res.status_code == 200
    data = res.json()
    assert data["specification"] == "AM-CP-v2.5"
    assert data["status"] == "HEALTHY"



def test_task_submission_and_retrieval():
    payload = {
        "tenant_id": "test_tenant",
        "cost_center": "cc_test",
        "agent_type": "code_reviewer",
        "priority": 3,
        "payload": {
            "instruction": "Review code for user john.doe@example.com with API key sk-12345678901234567890123456789012"
        }
    }

    res = client.post("/v1/tasks", json=payload)
    assert res.status_code == 201
    res_data = res.json()
    task_id = res_data["task_id"]
    assert res_data["status"] == "success"

    # Get details & verify PII redaction
    res_get = client.get(f"/v1/tasks/{task_id}")
    assert res_get.status_code == 200
    task_detail = res_get.json()
    assert "[REDACTED_EMAIL]" in task_detail["payload"]["instruction"]
    assert "[REDACTED_API_KEY]" in task_detail["payload"]["instruction"]


def test_hitl_approval_flow():
    payload = {
        "tenant_id": "prod_tenant",
        "agent_type": "deployer",
        "governance": {
            "require_hitl_for_tools": ["git_push_production"]
        },
        "payload": {
            "instruction": "Please git_push_production to main branch"
        }
    }

    # Submit task requiring HITL
    res = client.post("/v1/tasks", json=payload)
    assert res.status_code == 201
    res_data = res.json()
    task_id = res_data["task_id"]
    assert res_data["state"] == "WAITING_HITL"
    assert res_data["hitl_trigger_tool"] == "git_push_production"

    # Try poll - worker should not get it
    res_poll = client.post("/v1/workers/poll?worker_id=wrk_1&agent_type=deployer")
    assert res_poll.status_code == 200
    assert res_poll.json()["task"] is None

    # Submit HITL decision APPROVED
    res_hitl = client.post(f"/v1/hitl/{task_id}/decision", json={
        "decision": "APPROVED",
        "operator_id": "lead_dev",
        "reason": "Verified CI checks passed"
    })
    assert res_hitl.status_code == 200
    assert res_hitl.json()["new_state"] == "QUEUED"

    # Poll again - worker should get it now
    res_poll_after = client.post("/v1/workers/poll?worker_id=wrk_1&agent_type=deployer")
    assert res_poll_after.status_code == 200
    polled_task = res_poll_after.json()["task"]
    assert polled_task is not None
    assert polled_task["task_id"] == task_id


def test_mcp_tools_and_call():
    res_tools = client.get("/v1/mcp/tools?tenant_id=default_tenant")
    assert res_tools.status_code == 200
    tools = res_tools.json()
    assert len(tools) > 0

    res_call = client.post("/v1/mcp/tools/call", json={
        "tenant_id": "default_tenant",
        "tool_name": "query_db",
        "arguments": {"query": "SELECT * FROM users WHERE email = 'user@example.com'"},
        "pii_redact": True
    })
    assert res_call.status_code == 200
    call_result = res_call.json()
    assert call_result["success"] is True
    assert "[REDACTED_EMAIL]" in call_result["result_data"]["arguments"]["query"]


def test_metrics_and_prometheus():
    res_summary = client.get("/v1/metrics/summary")
    assert res_summary.status_code == 200
    assert "total_tasks" in res_summary.json()

    res_chargeback = client.get("/v1/metrics/chargeback?start_time=0")
    assert res_chargeback.status_code == 200
    assert "tenants" in res_chargeback.json()

    res_prom = client.get("/metrics")
    assert res_prom.status_code == 200
    assert "agentmesh_queued_tasks" in res_prom.text
