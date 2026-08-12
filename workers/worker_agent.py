import time
import requests
import json
import os
import sys

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8000")
WORKER_ID = os.getenv("WORKER_ID", "worker_node_daemon_01")
AGENT_TYPE = os.getenv("AGENT_TYPE", "general_worker")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2.0"))


def run_worker_loop():
    print(f"🤖 [AgentMesh Worker Daemon] Starting worker '{WORKER_ID}' for agent pool '{AGENT_TYPE}'")
    print(f"🔗 Connected to Control Plane at: {CONTROL_PLANE_URL}")

    while True:
        try:
            # Poll Control Plane for next queued task matching AGENT_TYPE
            poll_url = f"{CONTROL_PLANE_URL}/v1/workers/poll?worker_id={WORKER_ID}&agent_type={AGENT_TYPE}"
            res = requests.post(poll_url, timeout=5.0)

            if res.status_code == 200:
                data = res.json()
                task = data.get("task")

                if task:
                    task_id = task["task_id"]
                    instruction = task["payload"]["instruction"]
                    tenant_id = task["tenant_id"]

                    print(f"\n⚡ [TASK DEQUEUED] Task ID: {task_id} | Tenant: {tenant_id}")
                    print(f"   Instruction: {instruction}")

                    # Simulate agent processing & reasoning step
                    time.sleep(1.5)

                    # Submit task result back to Control Plane
                    result_payload = {
                        "status": "COMPLETED",
                        "output": f"Worker '{WORKER_ID}' successfully processed task: {instruction[:50]}...",
                        "agent_type": AGENT_TYPE
                    }

                    submit_url = (
                        f"{CONTROL_PLANE_URL}/v1/workers/submit-result"
                        f"?task_id={task_id}&status=COMPLETED"
                        f"&prompt_tokens=320&completion_tokens=140&cost_usd=0.008"
                        f"&worker_id={WORKER_ID}"
                    )
                    sub_res = requests.post(submit_url, json=result_payload, timeout=5.0)

                    if sub_res.status_code == 200:
                        print(f"✅ [TASK COMPLETED] Results submitted for task {task_id}")
                    else:
                        print(f"❌ [SUBMIT FAILED] Error: {sub_res.status_code} - {sub_res.text}")
                else:
                    # Idle heartbeat
                    pass
            else:
                print(f"⚠️ Poll error HTTP {res.status_code}")

        except Exception as e:
            print(f"⚠️ Worker communication error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_worker_loop()
