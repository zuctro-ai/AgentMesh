# Design Document: Zuctro AgentMesh Control Plane (AM-CP-v2.5)

## Overview

AgentMesh is a FastAPI-based Python service acting as a centralized control plane and governance gateway for multi-agent systems. It receives tasks from client SDKs or HTTP/gRPC callers, applies a declarative plugin pipeline (PII redaction, prompt injection shielding, token budgeting, HITL gating), routes tasks to a priority queue, dispatches them to worker nodes via polling, and records structured telemetry for chargeback and observability. The current codebase provides a working skeleton; this design covers the full AM-CP-v2.5 feature surface.

---

## Architecture

```
                        ┌────────────────────────────────────────────┐
                        │         REST / gRPC Ingress Layer          │
                        │  FastAPI (app.py) + gRPC server (grpc/)    │
                        └──────────────────┬─────────────────────────┘
                                           │
                                           ▼
                        ┌────────────────────────────────────────────┐
                        │       Declarative Plugin Pipeline          │
                        │  PluginEngine (core/plugins.py)            │
                        │  ┌────────────┐  ┌──────────────────────┐  │
                        │  │pii-redact  │→ │prompt-inject-shield  │  │
                        │  └────────────┘  └──────────────────────┘  │
                        │  ┌────────────┐  ┌──────────────────────┐  │
                        │  │token-budget│→ │hitl-approval-router  │  │
                        │  └────────────┘  └──────────────────────┘  │
                        └──────────────────┬─────────────────────────┘
                                           │
                                           ▼
                        ┌────────────────────────────────────────────┐
                        │    Priority Task Queue & Retry Engine      │
                        │    TaskOrchestrator (core/orchestrator.py) │
                        │    asyncio.PriorityQueue + DLQ routing     │
                        └──────────────────┬─────────────────────────┘
                                           │
                         ┌─────────────────┼──────────────────┐
                         ▼                 ▼                  ▼
              ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
              │ Worker Poll  │  │ HITL Decision API│  │  MCP Proxy GW   │
              │ /v1/workers  │  │ /v1/hitl/:id     │  │ /v1/mcp/...     │
              └──────────────┘  └──────────────────┘  └──────────────────┘
                                           │
                                           ▼
                        ┌────────────────────────────────────────────┐
                        │     Telemetry & State Store                │
                        │     DatabaseStore (core/database.py)       │
                        │     + ChargebackLedger + OTelEmitter       │
                        └────────────────────────────────────────────┘
```

---

## Components and Interfaces

### 1. `app.py` — REST Ingress Layer

Extends the current FastAPI app with the missing endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/v1/tasks` | POST | Submit a task through the plugin pipeline |
| `/v1/tasks/{task_id}` | GET | Retrieve task details |
| `/v1/tasks` | GET | List tasks with optional status filter |
| `/v1/tasks/{task_id}/stream` | GET | SSE stream of task status events |
| `/v1/workers/poll` | POST | Worker polls for next available task |
| `/v1/workers/submit-result` | POST | Worker submits task completion or failure |
| `/v1/workers` | GET | List all registered workers |
| `/v1/hitl/{task_id}/decision` | POST | Operator submits HITL approve/reject decision |
| `/v1/mcp/tools` | GET | Returns RBAC-filtered MCP tool list for tenant |
| `/v1/mcp/tools/call` | POST | Proxied MCP tool call with PII sanitization |
| `/v1/mcp/servers` | POST | Register external remote MCP server endpoint |
| `/v1/mcp/servers/{server_name}/sync` | POST | Discover remote MCP tools via JSON-RPC (`tools/list`) |
| `/v1/chat/completions` | POST | Governed OpenAI-compatible LLM Gateway proxy endpoint |
| `/v1/metrics/summary` | GET | System-level counters |
| `/v1/metrics/chargeback` | GET | Per-tenant/cost-center usage report |


### 2. `core/plugins.py` — Plugin Engine

New file. Owns plugin pipeline execution.

```python
class PluginEngine:
    def load_binding(self, yaml_str: str) -> AgentPluginBinding: ...
    def run_pipeline(self, task: AgentTask) -> PluginResult: ...
```

`PluginResult` carries: `allowed: bool`, `modified_task: AgentTask`, `redactions: List[str]`, `injection_score: float`, `audit_events: List[AuditEvent]`.

Plugins execute in declared order. Each plugin is a class implementing:

```python
class BasePlugin:
    name: str
    def execute(self, task: AgentTask, config: dict) -> PluginResult: ...
```

Concrete implementations: `PIIRedactionPlugin`, `PromptInjectionShieldPlugin`, `TokenBudgetCapperPlugin`, `HITLApprovalRouterPlugin`, `MCPToolFilterPlugin`.

### 3. `core/governance.py` — Governance Interceptor (extended)

Adds:
- `check_prompt_injection(text: str, threshold: float) -> Tuple[bool, float]` — pattern-based heuristic scoring
- `check_budget_on_result(task, tokens, cost) -> bool` — used by orchestrator after result submission

### 4. `core/orchestrator.py` — Task Orchestrator (extended)

Adds:
- `pause_task_for_hitl(task_id: str, tool_name: str) -> AgentTask` — sets `WAITING_HITL`, records trigger tool
- `resume_task_from_hitl(task_id: str, decision: str, operator_id: str, reason: str) -> AgentTask` — APPROVED → QUEUED, REJECTED → FAILED
- `expire_stale_hitl_tasks(timeout_seconds: int)` — background coroutine scanning WAITING_HITL tasks
- `expire_stale_workers(timeout_seconds: int)` — background coroutine for worker heartbeat expiry
- `event_bus: Dict[str, asyncio.Queue]` — per-task SSE event queues for streaming

### 5. `core/database.py` — State Store (extended)

Adds:
- `ChargebackRecord(BaseModel)` — per-task attribution: `task_id`, `tenant_id`, `cost_center`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `timestamp`
- `save_chargeback(record: ChargebackRecord)` and `get_chargeback_report(start_time: float) -> dict`
- `save_worker(worker: WorkerInfo)` and `get_all_workers() -> List[WorkerInfo]`
- `update_worker_status(worker_id, status, task_id)`

### 6. `core/mcp_gateway.py` — MCP Proxy Gateway (new)

```python
class MCPGateway:
    def list_tools(self, tenant_id: str, rbac_policy: dict) -> List[MCPTool]: ...
    def call_tool(self, tenant_id: str, tool_name: str, arguments: dict,
                  pii_redact: bool) -> MCPToolResult: ...
```

Forwards calls over HTTP/SSE to upstream MCP server URLs registered in `mcp_registry`.

### 7. `core/telemetry.py` — OTel Emitter (new)

```python
class OTelEmitter:
    def emit_task_span(self, task: AgentTask, prev_status: TaskStatus, 
                       new_status: TaskStatus) -> None: ...
    def emit_plugin_span(self, plugin_name: str, task_id: str, 
                         result: PluginResult) -> None: ...
```

Uses `opentelemetry-sdk` with `ConsoleSpanExporter` as default; configurable via env var `OTEL_EXPORTER_OTLP_ENDPOINT`.

### 8. `grpc/server.py` — gRPC Service (new)

Implements `AgentMeshControlPlane` service from `agentmesh.v2.proto`:
- `SubmitTask` → delegates to `orchestrator.submit_task`
- `PollTask` → delegates to `orchestrator.get_next_task_for_worker`
- `SubmitResult` → delegates to `orchestrator.process_task_result`
- `SubmitHITLDecision` → delegates to `orchestrator.resume_task_from_hitl`
- `StreamTaskEvents` → yields from per-task event queue

### 9. `core/models.py` — Data Models (extended)

Adds:
- `AgentPluginBinding(BaseModel)` — YAML-mapped plugin config
- `PluginConfig(BaseModel)` — individual plugin name + config dict
- `HITLDecision(BaseModel)` — `task_id`, `decision` (APPROVED/REJECTED), `operator_id`, `reason`
- `ChargebackRecord(BaseModel)` — attribution record
- `MCPTool(BaseModel)`, `MCPToolCallRequest(BaseModel)`, `MCPToolResult(BaseModel)`
- `TaskEvent(BaseModel)` — SSE event payload
- `cost_center: str` field added to `AgentTask`
- `hitl_trigger_tool: Optional[str]` field added to `AgentTask`

---

## Data Models

### AgentTask (extended)

```python
class AgentTask(BaseModel):
    task_id: str
    parent_task_id: Optional[str]
    tenant_id: str
    cost_center: str = "default"          # NEW: chargeback attribution
    agent_type: str
    assigned_worker_id: Optional[str]
    status: TaskStatus
    priority: int
    retries: int
    max_retries: int
    hitl_trigger_tool: Optional[str]       # NEW: tool that triggered HITL pause
    governance: GovernancePolicy
    payload: TaskPayload
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    telemetry: TelemetryMetrics
    created_at: float
    updated_at: float
    completed_at: Optional[float]
```

### AgentPluginBinding

```python
class PluginConfig(BaseModel):
    name: str
    enabled: bool = True
    config: Dict[str, Any] = {}

class AgentPluginBinding(BaseModel):
    name: str
    target_agent_type: str = "*"
    plugins: List[PluginConfig]
```

### ChargebackRecord

```python
class ChargebackRecord(BaseModel):
    task_id: str
    tenant_id: str
    cost_center: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    timestamp: float
```

### TaskEvent (SSE payload)

```python
class TaskEvent(BaseModel):
    task_id: str
    status: str
    tenant_id: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    timestamp: str   # ISO-8601
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: PII Redaction Completeness

*For any* task instruction string containing one or more PII tokens (email, phone, API key, credit card), after the PII redaction plugin executes, the resulting instruction string SHALL contain zero matches against the original PII patterns.
**Validates: Requirements 1.2**

### Property 2: Whitespace-Only and Empty Instructions are Rejected

*For any* task instruction composed entirely of whitespace characters, the governance pipeline SHALL reject the task and the task queue length SHALL remain unchanged.
**Validates: Requirements 1.3, 1.4**

### Property 3: Token Budget Enforcement Routes to DLQ

*For any* task with a finite `max_token_budget`, if the cumulative tokens reported across sequential result submissions exceed `max_token_budget`, the task SHALL ultimately transition to `DEAD_LETTER_QUEUE` status.
**Validates: Requirements 2.5**

### Property 4: Cost Cap Enforcement Routes to DLQ

*For any* task with a finite `max_cost_usd`, if the cumulative cost reported across sequential result submissions exceeds `max_cost_usd`, the task SHALL ultimately transition to `DEAD_LETTER_QUEUE` status.
**Validates: Requirements 2.6**

### Property 5: Priority Queue Ordering

*For any* set of enqueued tasks with distinct priorities, the polling order SHALL be strictly non-increasing in priority value (highest priority task always dequeued first).
**Validates: Requirements 2.1**

### Property 6: Retry Count Monotonically Increases to DLQ

*For any* task configured with `max_retries = N`, submitting N+1 consecutive FAILED results SHALL result in the task reaching `DEAD_LETTER_QUEUE` status with a retry count equal to N.
**Validates: Requirements 2.3, 2.4**

### Property 7: HITL Pause Prevents Worker Dequeue

*For any* task in `WAITING_HITL` status, a worker poll for the matching `agent_type` SHALL NOT return that task.
**Validates: Requirements 3.2**

### Property 8: HITL Round-Trip (Approve Restores Queueable State)

*For any* task transitioned to `WAITING_HITL`, submitting an APPROVED decision SHALL transition the task to `QUEUED` status, and the task SHALL subsequently be returned by the next matching worker poll.
**Validates: Requirements 3.3**

### Property 9: Chargeback Attribution Consistency

*For any* completed task with a non-default `tenant_id` and `cost_center`, the chargeback ledger entry for that task SHALL record the same `tenant_id`, `cost_center`, `prompt_tokens`, `completion_tokens`, and `cost_usd` as the task's `TelemetryMetrics`.
**Validates: Requirements 5.2**

### Property 10: Plugin YAML Round-Trip

*For any* valid `AgentPluginBinding` object, serializing it to YAML and deserializing it back SHALL produce an object that is semantically equivalent to the original.
**Validates: Requirements 7.5**

### Property 11: Task JSON Round-Trip

*For any* valid `AgentTask` object, serializing it to JSON and deserializing it back SHALL produce an object that is semantically equivalent to the original.
**Validates: Requirements 9.4, 5.6**

### Property 12: gRPC TaskEnvelope Round-Trip

*For any* valid `TaskEnvelope` message, serializing it via protobuf and deserializing it SHALL produce a `TaskEnvelope` that is semantically equivalent to the original.
**Validates: Requirements 9.3**

### Property 13: SSE Stream Completeness

*For any* task that transitions through a sequence of statuses and reaches a terminal state, a connected SSE client SHALL receive one event per status transition and a final event at the terminal state, with no duplicate or missing events.
**Validates: Requirements 8.1, 8.2**

### Property 14: MCP Tool Filter Restricts to Allowlist

*For any* tenant with a non-empty tool allowlist and a registry containing tools both inside and outside the allowlist, the filtered tool list returned SHALL contain only tools present in the tenant's allowlist.
**Validates: Requirements 4.1**

---

## Error Handling

| Scenario | HTTP Status | Behavior |
|---|---|---|
| Invalid task fields (missing instruction) | 422 | Pydantic validation error returned |
| Token budget ≤ 0 | 422 | Governance rejection with message |
| Cost cap ≤ 0 | 422 | Governance rejection with message |
| Prompt injection detected (ENFORCE mode) | 422 | Plugin rejection with injection score |
| Task not found | 404 | Standard HTTP 404 |
| Worker submits result for unknown task_id | 404 | Error response |
| HITL decision on non-WAITING_HITL task | 409 | Conflict error with current status |
| Budget exceeded mid-execution | DLQ transition | Task moved to DLQ, error_message populated |
| HITL timeout | FAILED transition | error_message = "HITL approval timed out" |
| Worker heartbeat timeout | OFFLINE transition | Worker status set to OFFLINE |
| gRPC field missing | gRPC INVALID_ARGUMENT | Standard gRPC error status |

---

## Testing Strategy

### Property-Based Testing

The project SHALL use **[Hypothesis](https://hypothesis.readthedocs.io/)** as the property-based testing library for Python.

Each property-based test SHALL:
- Run a minimum of 100 iterations (configured via `@settings(max_examples=100)`)
- Be tagged with a comment in the exact format: `**Feature: agentmesh-control-plane, Property {N}: {property_text}**`
- Be implemented as a single test function per correctness property
- Use Hypothesis strategies to generate `AgentTask`, `GovernancePolicy`, `AgentPluginBinding`, and other domain objects with realistic constraints

Example tag format:
```python
# **Feature: agentmesh-control-plane, Property 1: PII Redaction Completeness**
@given(instruction=st.text())
@settings(max_examples=100)
def test_pii_redaction_completeness(instruction):
    ...
```

### Unit Tests

Unit tests SHALL use **pytest** and cover:
- Specific governance rejection cases (zero budget, zero cost cap)
- HITL state machine transitions (pending → HITL → queued, pending → HITL → failed)
- DLQ routing after max retries
- Chargeback ledger accumulation
- MCP tool filtering with explicit allowlists
- SSE event emission sequence for a task lifecycle

### Test File Layout

```
tests/
├── test_governance.py          # Unit + property tests for governance interceptor
├── test_orchestrator.py        # Unit + property tests for queue and retry engine
├── test_plugins.py             # Unit + property tests for plugin pipeline
├── test_mcp_gateway.py         # Unit + property tests for MCP proxy
├── test_telemetry.py           # Unit tests for OTel emitter and chargeback
├── test_models.py              # Property tests for JSON/YAML round-trips
├── test_api.py                 # Integration tests for REST endpoints (TestClient)
├── test_cli.py                 # Unit tests for global CLI tool
└── test_grpc.py                # Integration tests for gRPC service
```

---

## 🚀 Zuctro AgentMesh v3.0 Strategic Enterprise Roadmap

1. **🔑 Enterprise Authentication & Multi-Tenant RBAC (Okta / Auth0 / Keycloak):** API Keys & Bearer JWT Validation, Granular Scopes (`agentmesh:task:submit`, `agentmesh:hitl:approve`, `agentmesh:mcp:admin`), and Tenant Cryptographic Isolation.
2. **🗄️ Production Distributed Storage Backing (Redis & PostgreSQL):** Redis Streams / PubSub task queue, PostgreSQL audit ledger for task history, HITL decision logs, and FinOps chargeback.
3. **☸️ Production Helm Chart & KEDA Kubernetes Auto-scaler CRD:** `charts/agentmesh` Helm deployment on EKS/GKE/AKS with KEDA ScaledObjects (`agentmesh_queued_tasks > 0`) and gVisor/Kata sandbox isolation.
4. **🔔 Interactive Slack & Teams HITL Approval Bot:** Real-time Slack/Teams notifications when HITL triggers occur; interactive "Approve" / "Reject" buttons inside chat channels.
5. **🧠 Semantic LLM Prompt Caching & Smart Model Router:** Vector similarity prompt caching (Redis/Qdrant) cutting token costs by up to 80%, combined with dynamic model routing (`gpt-4o-mini` vs `claude-3.5-sonnet`).
6. **📊 Real-Time LLM Quality & Hallucination Guardrails (Eval Engine):** Automated quality scoring for completed task outputs and automatic retry/DLQ routing on hallucination thresholds.

