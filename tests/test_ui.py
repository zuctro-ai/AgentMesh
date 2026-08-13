"""
Zuctro AgentMesh - UI HTML & Dashboard API Route Test Suite
"""

import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_ui_index_html_serving():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "Zuctro AgentMesh" in html
    assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()


def test_ui_static_assets():
    css_res = client.get("/static/styles.css")
    assert css_res.status_code == 200
    assert len(css_res.text) > 50

    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200
    assert len(js_res.text) > 50


def test_ui_interactive_flow_task_submission_and_hitl():
    # 1. Submit task through task submission API (equivalent to UI form submission)
    task_payload = {
        "agent_type": "general_worker",
        "priority": 5,
        "tenant_id": "ui_tenant",
        "cost_center": "ui_cc",
        "payload": {
            "instruction": "UI Test Task: Perform security sweep",
            "context": {"source": "web_ui"}
        },
        "governance": {
            "max_token_budget": 5000,
            "max_cost_usd": 0.50,
            "pii_redaction": True
        }
    }

    sub_res = client.post("/v1/tasks", json=task_payload)
    assert sub_res.status_code == 201
    task_data = sub_res.json()
    task_id = task_data["task_id"]
    assert task_data["status"] == "success"

    # 2. Get task list for UI table
    list_res = client.get("/v1/tasks")
    assert list_res.status_code == 200
    tasks = list_res.json()
    found = any(t["task_id"] == task_id for t in tasks)
    assert found is True

    # 3. Create and pause task for HITL approval
    hitl_task_payload = {
        "agent_type": "general_worker",
        "priority": 9,
        "tenant_id": "ui_tenant",
        "cost_center": "ui_cc",
        "payload": {
            "instruction": "UI HITL Test: execute_sql_mutation DROP TABLE accounts;",
            "context": {"source": "web_ui"}
        },
        "governance": {
            "max_token_budget": 5000,
            "max_cost_usd": 0.50,
            "pii_redaction": True
        }
    }
    hitl_sub_res = client.post("/v1/tasks", json=hitl_task_payload)
    assert hitl_sub_res.status_code == 201
    hitl_task_data = hitl_sub_res.json()
    hitl_task_id = hitl_task_data["task_id"]

    # Pause task for HITL tool interception
    import asyncio
    from core.orchestrator import orchestrator
    asyncio.run(orchestrator.pause_task_for_hitl(hitl_task_id, "execute_sql_mutation"))

    # 4. Submit operator approval decision (clicking "Approve" in UI)
    dec_res = client.post(f"/v1/hitl/{hitl_task_id}/decision", json={
        "decision": "APPROVED",
        "operator_id": "ui_operator_admin",
        "reason": "Approved via UI Dashboard"
    })
    assert dec_res.status_code == 200
    assert dec_res.json()["new_state"] == "QUEUED"


    # 5. Check metrics summary for UI header counters
    metrics_res = client.get("/v1/metrics/summary")
    assert metrics_res.status_code == 200
    summary = metrics_res.json()
    assert "total_tasks" in summary
    assert "total_tokens_burned" in summary

