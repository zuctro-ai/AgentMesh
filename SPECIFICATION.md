# Zuctro AgentMesh Enterprise Specification Standard (AM-CP-v2.5 & AM-K8S-v2.5)

- **Company & Specification Brand:** Zuctro AI (https://zuctro.ai)
- **Specification Version:** 2.5.0-ENTERPRISE-STANDARD
- **Standards:** AM-CP-v2.5 (Control Plane & Plugin Standard), AM-K8S-v2.5 (Kubernetes Operator & KEDA Scale-to-Zero), AM-MCP-v1.0 (Model Context Protocol Gateway Standard), AM-A2A-v1.0 (Agent-to-Agent Federation)
- **Status:** Complete Enterprise Open Standard Specification
- **Target Audience:** Enterprise AI Engineers, Platform Architects, Security & AI Governance Directors, Cloud Infrastructure Engineers

---

## 1. Executive Vision: Enterprise Gateway & Control Plane for Multi-Agent Systems

**Zuctro AgentMesh** acts as the definitive **Enterprise Gateway & Control Plane for Multi-Agent Systems**, decoupling agent reasoning logic from infrastructure, security, rate limiting, and governance.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     ENTERPRISE INGRESS GATEWAY (RBAC)                                       │
│                       [ OAuth2 / mTLS | Tenant Isolation | Declarative YAML Policies ]                      │
└───────────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                DECLARATIVE PLUGIN INTERCEPTOR PIPELINE                                      │
│                                                                                                             │
│ ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────────┐ │
│ │ plugin: pii-redact   │─▶│ plugin: prompt-shield│─▶│ plugin: mcp-filter   │─▶│ plugin: token-budget-cap │ │
│ └──────────────────────┘  └──────────────────────┘  └──────────────────────┘  └──────────────────────────┘ │
└───────────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 LLM ROUTING GATEWAY & SEMANTIC CACHE                                        │
│               [ Multi-Provider Failover | Cost/Showback Ledger | Vector Completion Cache ]                  │
└───────────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  DISTRIBUTED TASK MESH QUEUE & DLQ                                          │
│                 [ Priority Queue | Exponential Retries | HITL Pauser | Dead Letter Queue ]                  │
└───────────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                                    │ Metrics Trigger (Queued Tasks > 0)
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               KUBERNETES OPERATOR & KEDA (DYNAMIC LIFECYCLE)                                │
│       [ Scale-to-Zero Pods | Dynamic Spin-Up/Down | gVisor Sandbox Isolation | Confidential Compute ]       │
└───────────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                                    │ Poll & Execute
                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        AGENT WORKER RUNTIMES                                                │
│    ┌───────────────────────────┐      ┌───────────────────────────┐      ┌────────────────────────────┐     │
│    │ Worker Node (LangGraph)   │      │ Worker Node (CrewAI/Node) │      │ Worker Node (Go/Rust/MCP)  │     │
│    └─────────────┬─────────────┘      └─────────────┬─────────────┘      └─────────────┬──────────────┘     │
└──────────────────┼──────────────────────────────────┼────────────────────┼──────────────────────────────────┘
                   │                                  │                    │
                   └──────────────────────────────────┴────────────────────┘
                                                      │ OpenTelemetry AI Spans
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                OBSERVABILITY & CHARGEBACK ENGINE                                            │
│            [ OTel Trace Visualizer | Prometheus Metrics | Department Showback/Chargeback Ledger ]           │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Declarative Plugin Architecture

All governance, security, and routing rules in Zuctro AgentMesh are specified as **Declarative Plugins** in YAML format (reusable across clusters via GitOps/decK).

### 2.1 Core Plugin Matrix

| Plugin Name | Category | Functionality |
| :--- | :--- | :--- |
| `pii-redaction` | Security | Intercepts prompts/responses; masks Emails, SSN, API Keys, Credit Cards using regex & ML models. |
| `prompt-injection-shield` | Security | Scans payloads for OWASP LLM-01 prompt injections, jailbreaks, and policy overrides (`ENFORCE` / `SHADOW`). |
| `token-budget-capper` | Governance | Enforces hard max token and financial USD caps per task, user, or department. |
| `mcp-tool-filter` | Tool Gateway | Proxy for Model Context Protocol (MCP); inspects, filters, and logs agent tool execution parameters. |
| `hitl-approval-router` | Governance | Pauses task execution in `WAITING_HITL` state when agents request high-risk tool execution. |
| `llm-semantic-cache` | Optimization | Vector similarity cache for LLM prompt completions; cuts duplicate LLM calls by up to 40%. |
| `llm-provider-failover` | Reliability | Automatic fallback routing (e.g. Primary: OpenAI -> Secondary: Anthropic -> Tertiary: local vLLM). |
| `showback-chargeback` | Finance | Tags every token and cent to a specific enterprise `cost_center` and `department_id`. |

---

### 2.2 Declarative Plugin Config Spec (YAML)

```yaml
apiVersion: agentmesh.io/v2alpha1
kind: AgentPluginBinding
metadata:
  name: global-enterprise-guardrails
  namespace: agentmesh-system
spec:
  targetAgentType: "*" # Applies to all registered agent pools
  plugins:
    - name: pii-redaction
      enabled: true
      config:
        redactTypes: ["EMAIL", "PHONE", "API_KEY", "CREDIT_CARD"]
        maskReplacement: "[REDACTED]"
    
    - name: prompt-injection-shield
      enabled: true
      config:
        action: "ENFORCE" # "ENFORCE" (Block) or "SHADOW" (Audit log only)
        sensitivityThreshold: 0.85
        
    - name: token-budget-capper
      enabled: true
      config:
        maxTokensPerTaskChain: 100000
        maxCostUsdPerTaskChain: 2.00
        onExceeded: "ROUTE_TO_DLQ"

    - name: hitl-approval-router
      enabled: true
      config:
        requireHitlTools:
          - "execute_sql_mutation"
          - "git_push_production"
          - "deploy_cloud_infrastructure"
        approvalTimeoutSeconds: 86400
```

---

## 3. Kubernetes Operator & Scale-to-Zero Pod Lifecycle (AM-K8S-v2.5)

Zuctro AgentMesh features a **native Kubernetes Operator** that manages dynamic worker pod lifecycles via KEDA (Kubernetes Event-Driven Autoscaling).

### 3.1 Scale-to-Zero Lifecycle Sequence

```
           [Task Queue Depth = 0]
                      │
                      ▼ (Worker Replicas = 0 | $0 Compute Burn)
             Client Submits Task
                      │
                      ▼
     Control Plane Enqueues Task (Queue Depth = 1)
                      │
                      ▼
     Prometheus Metric `agentmesh_queued_tasks` > 0
                      │
                      ▼
     KEDA Triggers Kubernetes Pod Scale-Up (0 ──▶ N Pods)
                      │
                      ▼
     Worker Pod Spawns in Sandboxed Runtime (gVisor/Kata)
                      │
                      ▼
     Worker Polls Task ──▶ Executes Agent Loop ──▶ Submits Result
                      │
                      ▼
     Queue Becomes Empty (Queue Depth = 0)
                      │
                      ▼
     Cooldown Timer (e.g. 30s) Expires ──▶ KEDA Scales Pods Back to 0
```

---

### 3.2 `AgentDeployment` Kubernetes Custom Resource (CRD)

```yaml
apiVersion: agentmesh.io/v2alpha1
kind: AgentDeployment
metadata:
  name: code-reviewer-worker-pool
  namespace: agentmesh-production
spec:
  agentType: "code_reviewer"
  minReplicas: 0 # Enables Scale-to-Zero
  maxReplicas: 25
  cooldownPeriodSeconds: 30
  sandboxRuntime: "gvisor" # Isolates worker container from host kernel
  pluginBindingRef: "global-enterprise-guardrails"
  template:
    spec:
      containers:
        - name: agent-worker
          image: ghcr.io/zuctro/code-reviewer-worker:v2.5.0
          env:
            - name: AGENTMESH_CONTROL_PLANE_URL
              value: "http://agentmesh-gateway.agentmesh-system.svc.cluster.local:8000"
          resources:
            limits:
              cpu: "2"
              memory: "4Gi"
            requests:
              cpu: "250m"
              memory: "512Mi"
```

---

## 4. Model Context Protocol (MCP) & Agent-to-Agent (A2A) Gateway Standard

Zuctro AgentMesh natively functions as an **MCP Gateway Proxy (AM-MCP-v1.0)** and **A2A Service Mesh**:

```
 ┌──────────────────────┐         ┌──────────────────────────────────────┐         ┌──────────────────────┐
 │                      │  stdio  │    ZUCTRO MCP PROXY GATEWAY          │  HTTP   │                      │
 │ Agent Worker Node    │────────▶│  [ RBAC | PII | HITL | Audit Log ]   │────────▶│ Enterprise MCP Server│
 │ (LangGraph/CrewAI)   │  /SSE   │                                      │  /gRPC  │ (Postgres/GitHub)    │
 └──────────────────────┘         └──────────────────────────────────────┘         └──────────────────────┘
```

### 4.1 MCP Proxy Gateway Architecture
1. **Centralized Tool Registry:** Instead of configuring MCP server endpoints in every individual agent codebase, agents connect to Zuctro AgentMesh as their central MCP Gateway.
2. **Tool Discovery Filtering (`tools/list`):** When an agent requests available tools, Zuctro AgentMesh filters the list based on the caller's tenant RBAC policy.
3. **Tool Call Interception (`tools/call`):**
   - **Parameter Sanitization:** Automatically redacts PII from arguments passed to MCP tools.
   - **HITL Interception:** If a tool call targets a high-risk MCP capability (e.g. `postgres.drop_table`), Zuctro AgentMesh pauses execution and requires operator sign-off before forwarding the request to the upstream MCP Server.
4. **Supported MCP Transports:** `stdio`, `HTTP + SSE`, and `gRPC`.

---

### 4.2 Federated Agent-to-Agent (A2A) Mesh
- **Agent Identity (SPIFFE/mTLS):** Workers authenticate using SPIFFE IDs (`spiffe://cluster.local/ns/agentmesh/sa/coder`).
- **Scoped Delegation:** Parent agents delegating tasks to child agents issue short-lived JWT scoped tokens containing strict governance rules.

---

## 5. Enterprise Telemetry & Showback/Chargeback Engine

### 5.1 OpenTelemetry AI Span Tree

```
[Trace ID: am_tr_77f92a10]
 ├── Span: ingress.submit_task (tenant: fin_tech, cost_center: cc_402)
 ├── Span: plugin.pii_redaction (emails_masked: 1)
 ├── Span: plugin.prompt_injection_shield (jailbreak_score: 0.02, status: PASS)
 ├── Span: queue.enqueue (priority: 5, status: QUEUED)
 ├── Span: k8s.operator.scale_up (spawned_pod: code-reviewer-pod-99x)
 ├── Span: worker.execute (agent_type: code_reviewer)
 │    ├── Span: llm_proxy.request (model: gpt-4o, cache: MISS, prompt_tokens: 1200)
 │    ├── Span: mcp.tool_call (mcp_server: postgres_mcp, tool: query_db, duration_ms: 120)
 │    └── Span: plugin.hitl_approval (tool: deploy_prod, decision: APPROVED)
 └── Span: task.complete (total_tokens: 1450, total_cost_usd: 0.0145)
```

---

### 5.2 Enterprise Showback / Chargeback Metrics API

`GET /v1/metrics/chargeback?start_time=1770700000`

```json
{
  "period_start": 1770700000,
  "tenants": [
    {
      "tenant_id": "org_engineering",
      "cost_center": "cc_101",
      "total_tasks": 4500,
      "prompt_tokens": 14200000,
      "completion_tokens": 3100000,
      "total_cost_usd": 42.185,
      "breakdown_by_model": {
        "gpt-4o": 35.10,
        "claude-3-5-sonnet": 7.085
      }
    }
  ]
}
```

---

## 6. gRPC Protocol Contract (`agentmesh.v2.proto`)

```protobuf
syntax = "proto3";

package agentmesh.v2;

option go_package = "github.com/zuctro/agentmesh/gen/v2;agentmeshv2";

service AgentMeshControlPlane {
  rpc SubmitTask (SubmitTaskRequest) returns (SubmitTaskResponse);
  rpc PollTask (PollTaskRequest) returns (PollTaskResponse);
  rpc SubmitResult (SubmitResultRequest) returns (SubmitResultResponse);
  rpc SubmitHITLDecision (HITLDecisionRequest) returns (HITLDecisionResponse);
  rpc StreamTaskEvents (StreamTaskEventsRequest) returns (stream TaskEvent);
}

message TaskEnvelope {
  string task_id = 1;
  string parent_task_id = 2;
  string tenant_id = 3;
  string cost_center = 4;
  string agent_type = 5;
  int32 priority = 6;
  string status = 7;
  string instruction = 8;
  string context_json = 9;
  int64 created_at = 10;
}

message SubmitTaskRequest {
  TaskEnvelope task = 1;
}

message SubmitTaskResponse {
  string task_id = 1;
  string status = 2;
  string message = 3;
}

message PollTaskRequest {
  string worker_id = 1;
  string agent_type = 2;
}

message PollTaskResponse {
  TaskEnvelope task = 1;
}

message SubmitResultRequest {
  string worker_id = 1;
  string task_id = 2;
  string status = 3;
  string result_json = 4;
  int32 prompt_tokens = 5;
  int32 completion_tokens = 6;
  double cost_usd = 7;
  string error_message = 8;
}

message SubmitResultResponse {
  bool acknowledged = 1;
}

message HITLDecisionRequest {
  string task_id = 1;
  string decision = 2;
  string operator_id = 3;
  string reason = 4;
}

message HITLDecisionResponse {
  bool success = 1;
  string new_status = 2;
}

message StreamTaskEventsRequest {
  string task_id = 1;
}

message TaskEvent {
  string task_id = 1;
  string status = 2;
  int32 prompt_tokens = 3;
  int32 completion_tokens = 4;
  double cost_usd = 5;
  string payload_json = 6;
}
```

---

## 7. Conformance Verification & Compliance Suite

An implementation achieves **Zuctro AgentMesh AM-CP-v2.5 Certification** by passing 10 automated test benchmarks:

8. Global Command Line Interface (`agentmesh` CLI Spec)
------------------------------------------------------

Zuctro AgentMesh includes a native, standalone global CLI tool (`agentmesh`) packaged via PyPI / `setup.py` entry points.

```bash
# 1. Health & Metrics Inspection
agentmesh status

# 2. Submit Task & Stream SSE Events
agentmesh task submit -i "Sanitize customer ticket JIRA-102" --agent-type data_analyst --follow

# 3. Task Management & Inspection
agentmesh task list --status WAITING_HITL
agentmesh task inspect tsk_55436075
agentmesh task stream tsk_55436075

# 4. Human-in-the-Loop Operator Gate Management
agentmesh hitl list
agentmesh hitl approve tsk_af2bd402 --operator sec_admin --reason "Ticket CHG-9921 approved"
agentmesh hitl reject tsk_af2bd402 --reason "Disallowed database drop"

# 5. Model Context Protocol Tool Discovery
agentmesh mcp list
```

---

## 9. Governed OpenAI-Compatible LLM Gateway Proxy (`POST /v1/chat/completions`)

Zuctro AgentMesh provides an inline **Governed LLM Gateway Proxy** compatible with standard OpenAI SDKs, LangChain, CrewAI, and AutoGen.

```
Client App (OpenAI SDK) ──▶ POST /v1/chat/completions (AgentMesh Proxy) ──▶ Upstream Target LLM Engine
```

### 9.1 Inline Governance Pipeline:
1. **OWASP Prompt Injection Check:** Rejects injection attacks inline with `HTTP 422`.
2. **Inline PII Sanitization:** Redacts sensitive email addresses, phone numbers, credit card details, and SSNs.
3. **Usage & FinOps Attribution:** Automatically logs prompt/completion tokens and attributes cost ($) to `x-tenant-id` and `x-cost-center`.

---

## 10. Remote Model Context Protocol (MCP) Server Integration

Zuctro AgentMesh acts as a centralized **MCP Gateway Proxy (AM-MCP-v1.0)** supporting remote MCP servers over HTTP, SSE, and stdio JSON-RPC.

### 10.1 Remote Server Registration & Tool Discovery (`tools/list`):
- `POST /v1/mcp/servers`: Register external MCP endpoints (e.g. Jira MCP, Confluence MCP, Postgres MCP, GitHub MCP).
- `POST /v1/mcp/servers/{server_name}/sync`: Dynamically discover tools using standard MCP JSON-RPC (`tools/list`).
- Built-in parameter PII redaction and HITL authorization on tool dispatch (`POST /v1/mcp/tools/call`).

---

## 11. Zuctro AgentMesh v3.0 Architecture Roadmap

| Module | Feature | Target |
| :--- | :--- | :--- |
| **Storage & Queue** | Distributed Redis Streams & PostgreSQL persistent state storage | AM-CP-v3.0 |
| **Authentication** | Enterprise OAuth2 / OIDC JWT Auth Middleware & SPIFFE mTLS | AM-CP-v3.0 |
| **Autoscaling** | Production Helm Chart (`charts/agentmesh`) & KEDA ScaledObjects | AM-K8S-v3.0 |
| **HITL Gateway** | Interactive Slack & Microsoft Teams HITL Approval Bot | AM-CP-v3.0 |
| **LLM Optimization** | Vector Similarity Semantic Prompt Cache (Qdrant/Redis) | AM-CP-v3.0 |
| **Smart Routing** | Dynamic LLM Cost-to-Complexity Model Router (Sonnet vs Llama vs GPT-4o) | AM-CP-v3.0 |

---

> **Specification License:** Apache 2.0 (Open Source Infrastructure Standard)  
> **Brand & Copyright:** © Zuctro AI (https://zuctro.ai)

