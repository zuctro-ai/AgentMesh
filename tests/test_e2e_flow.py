import requests
import json
import time

BASE_URL = "http://localhost:8000"


def test_end_to_end_flow():
    print("=" * 60)
    print("🚀 STARTING AGENTMESH END-TO-END UI & INTEGRATION TEST")
    print("=" * 60)

    # 1. Health check
    res_root = requests.get(f"{BASE_URL}/api/info")
    assert res_root.status_code == 200
    print("1. [Health Check] Server status:", res_root.json()["status"])

    # 2. Submit Task with PII Data
    print("\n2. [Task Submission with PII]")
    pii_payload = {
        "tenant_id": "e2e_tenant_alpha",
        "cost_center": "cc_fintech_101",
        "agent_type": "data_analyst",
        "priority": 5,
        "governance": {
            "max_token_budget": 10000,
            "max_cost_usd": 0.20,
            "pii_redaction": True
        },
        "payload": {
            "instruction": "Process payout for user jane.doe@acme.org with phone 555-234-5678 and account 4532-9012-3456-7890"
        }
    }
    res_sub1 = requests.post(f"{BASE_URL}/v1/tasks", json=pii_payload)
    assert res_sub1.status_code == 201
    task_id1 = res_sub1.json()["task_id"]
    print(f"   Task submitted! Task ID: {task_id1} | Initial State: {res_sub1.json()['state']}")

    # Verify PII Masking
    res_get1 = requests.get(f"{BASE_URL}/v1/tasks/{task_id1}")
    instruction1 = res_get1.json()["payload"]["instruction"]
    print("   Sanitized Instruction:", instruction1)
    assert "[REDACTED_EMAIL]" in instruction1
    assert "[REDACTED_PHONE]" in instruction1

    # 3. Submit Task Requiring HITL Approval
    print("\n3. [Task Submission Requiring HITL Approval]")
    hitl_payload = {
        "tenant_id": "e2e_tenant_beta",
        "cost_center": "cc_security_202",
        "agent_type": "infra_deployer",
        "priority": 5,
        "governance": {
            "require_hitl_for_tools": ["execute_sql_mutation"]
        },
        "payload": {
            "instruction": "Execute action execute_sql_mutation to clean transaction table"
        }
    }
    res_sub2 = requests.post(f"{BASE_URL}/v1/tasks", json=hitl_payload)
    assert res_sub2.status_code == 201
    task_id2 = res_sub2.json()["task_id"]
    state2 = res_sub2.json()["state"]
    print(f"   Task submitted! Task ID: {task_id2} | State: {state2} | Trigger Tool: {res_sub2.json()['hitl_trigger_tool']}")
    assert state2 == "WAITING_HITL"

    # 4. Verify Worker Cannot Dequeue Task While Waiting HITL
    print("\n4. [Worker Polling Gating Check]")
    res_poll_gated = requests.post(f"{BASE_URL}/v1/workers/poll?worker_id=node_worker_01&agent_type=infra_deployer")
    assert res_poll_gated.status_code == 200
    assert res_poll_gated.json()["task"] is None
    print("   Worker poll returned None as expected (task blocked at HITL gate).")

    # 5. Operator Approves HITL Task
    print("\n5. [Operator HITL Gate Approval]")
    res_decision = requests.post(f"{BASE_URL}/v1/hitl/{task_id2}/decision", json={
        "decision": "APPROVED",
        "operator_id": "sec_operator_e2e",
        "reason": "Verified change ticket CHG-98421"
    })
    assert res_decision.status_code == 200
    new_state = res_decision.json()["new_state"]
    print(f"   HITL Decision submitted! New State: {new_state}")
    assert new_state == "QUEUED"

    # 6. Worker Node Polls Task
    print("\n6. [Worker Pod Task Dequeue]")
    res_poll = requests.post(f"{BASE_URL}/v1/workers/poll?worker_id=node_worker_01&agent_type=infra_deployer")
    polled_task = res_poll.json()["task"]
    assert polled_task is not None
    assert polled_task["task_id"] == task_id2
    print(f"   Worker 'node_worker_01' successfully polled task: {polled_task['task_id']}")

    # 7. Worker Node Submits Result
    print("\n7. [Worker Execution & Result Submission]")
    res_result = requests.post(
        f"{BASE_URL}/v1/workers/submit-result?task_id={task_id2}&status=COMPLETED&prompt_tokens=420&completion_tokens=150&cost_usd=0.012&worker_id=node_worker_01",
        json={"status": "SUCCESS", "output": "Database transaction table sanitized cleanly."}
    )
    assert res_result.status_code == 200
    completed_task = res_result.json()["task"]
    print(f"   Task completed! Status: {completed_task['status']}")
    assert completed_task["status"] == "COMPLETED"

    # 8. Test MCP Gateway Tool Proxy Call
    print("\n8. [MCP Gateway Tool Proxy Invocation]")
    res_mcp = requests.post(f"{BASE_URL}/v1/mcp/tools/call", json={
        "tenant_id": "e2e_tenant_alpha",
        "tool_name": "query_db",
        "arguments": {"query": "SELECT * FROM payments WHERE email = 'user@company.com'"},
        "pii_redact": True
    })
    assert res_mcp.status_code == 200
    mcp_res = res_mcp.json()
    print("   MCP Tool Result:", mcp_res["result_data"]["arguments"])
    assert "[REDACTED_EMAIL]" in mcp_res["result_data"]["arguments"]["query"]

    # 9. Verify Financial Chargeback Ledger & Prometheus Metrics
    print("\n9. [Chargeback Ledger & Prometheus Metrics Validation]")
    res_chargeback = requests.get(f"{BASE_URL}/v1/metrics/chargeback?start_time=0")
    assert res_chargeback.status_code == 200
    report = res_chargeback.json()
    print(f"   Chargeback Tenants Count: {len(report['tenants'])}")
    
    res_prom = requests.get(f"{BASE_URL}/metrics")
    assert res_prom.status_code == 200
    print("   Prometheus Metrics Output:")
    for line in res_prom.text.split("\n"):
        if line and not line.startswith("#"):
            print("  ", line)

    print("\n" + "=" * 60)
    print("✅ ALL END-TO-END SYSTEM STAGES VERIFIED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_end_to_end_flow()
