# AgentMesh: Architecture & System Design Plan

> **Vision:** AgentMesh is an open-source, production-ready **Control Plane and Governance Gateway for Multi-Agent Systems**. Just as **Kong** acts as an API Gateway and **Kubernetes** acts as a Container Orchestrator, AgentMesh acts as an **Agent Control Plane**—managing agent lifecycles, task queue routing, token budgeting, PII guardrails, and real-time observability without locking developers into a specific agent SDK.

---

## 1. High-Level System Architecture

```
                               ┌──────────────────────────────────────────────┐
                               │        CLI / REST / gRPC / UI Ingress        │
                               │  [ agentmesh CLI | Dashboard | OpenAI SDK ]  │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             AGENTMESH CONTROL PLANE GATEWAY (AM-CP-v2.5)                                    │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────┐  ┌───────────────────────────┐  ┌────────────────────────────────────────┐  │
│  │   Ingress REST & SSE API  │  │   Governed LLM Proxy      │  │   gRPC Control Plane Servicer          │  │
│  │   (FastAPI / SSE Stream)  │  │   (POST /v1/chat/compl)   │  │   (agentmesh.v2.proto)                 │  │
│  └─────────────┬─────────────┘  └─────────────┬─────────────┘  └───────────────────┬────────────────────┘  │
│                │                              │                                    │                       │
│                └──────────────────────────────┼────────────────────────────────────┘                       │
│                                               ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                 Declarative Plugin Pipeline Engine                                   │  │
│  │ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ │  │
│  │ │ plugin: pii-redact   │─▶ plugin: prompt-shield│─▶ plugin: token-budget │─▶ plugin: hitl-router│ │  │
│  │ └──────────────────────┘ └──────────────────────┘ └──────────────────────┘ └──────────────────────┘ │  │
│  └────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘  │
│                                               │                                                            │
│                                               ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                   Model Context Protocol (MCP) Gateway                               │  │
│  │       [ Jira / Confluence / GitHub / Postgres | Remote JSON-RPC Sync | PII Redaction | RBAC Filter ]   │  │
│  └────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘  │
│                                               │                                                            │
│                                               ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                  Distributed Task Queue & State Machine                              │  │
│  │                    [ Priority Queue | Exponential Retries | HITL Pauser | DLQ Routing ]             │  │
│  └────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────┼────────────────────────────────────────────────────────────┘
                                                │
                                                ▼ (KEDA Trigger: agentmesh_queued_tasks > 0)
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
    ┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
    │ Worker Node (Python SDK) │   │ Worker Node (Node/Go)    │   │ Worker Node (LangGraph)  │
    └──────────────────────────┘   └──────────────────────────┘   └──────────────────────────┘
```

---

## 2. Core Architectural Components

1. **Control Plane Gateway (Ingress & Governance Layer)**
   - **FastAPI REST/SSE Server (`app.py`):** Ingress endpoint handling task creation, polling, result reporting, and SSE streaming.
   - **Governed LLM Gateway Proxy (`POST /v1/chat/completions`):** OpenAI-compatible proxy executing PII redaction and prompt injection checks before forwarding requests.
   - **Standalone Global CLI Binary (`agentmesh`):** Terminal interface for task submission, HITL operator decisioning, and real-time SSE streaming.
   - **gRPC Control Plane (`grpc_service/`):** High-performance streaming interface enforcing `proto/agentmesh.v2.proto`.

2. **Governance Interceptor & Declarative Plugin Engine (`core/plugins.py`)**
   - **PII Redactor:** Sanitizes email, phone numbers, credit card details, SSNs, and API keys.
   - **OWASP Prompt Injection Shield:** Scans payloads for malicious prompt overrides and jailbreaks.
   - **Token Budget & Cost Guardrails:** Hard capping max tokens and financial costs per task/tenant.
   - **HITL Gate Router:** Pauses high-risk operations (e.g., database mutations, cloud deployments, code releases) until operator approval.

3. **Model Context Protocol (MCP) Proxy Gateway (`core/mcp_gateway.py`)**
   - **Enterprise Tool Registry:** Built-in tool schemas for Jira, Confluence, GitHub, and SQL databases.
   - **Remote Server Discovery (`tools/list`):** Dynamic tool synchronization with remote standard MCP servers via JSON-RPC.
   - **Tool Parameter PII Redaction:** Automatically scrubs arguments before tool execution.

4. **Execution & Orchestration Engine (`core/orchestrator.py`)**
   - Priority queue dispatching, retry engine with exponential backoff, HITL task hold state, and Dead Letter Queue (DLQ) routing.

5. **Telemetry & FinOps Accounting (`core/telemetry.py`, `core/database.py`)**
   - OpenTelemetry GenAI span emitters, Prometheus `/metrics` exporter, and multi-tenant financial chargeback ledger.

