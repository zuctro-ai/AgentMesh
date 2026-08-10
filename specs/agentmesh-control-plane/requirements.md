# Requirements Document

## Introduction

Zuctro AgentMesh is an open-source, production-grade Agent Control Plane and Governance Gateway for enterprise multi-agent systems. It acts as a centralized ingress gateway, security interceptor, task orchestrator, and observability engine for AI agents built in any SDK or language. The system manages agent lifecycles, enforces governance policies (PII redaction, prompt injection shielding, token budgeting, HITL approvals), proxies Model Context Protocol (MCP) tool calls, and provides real-time telemetry with enterprise showback/chargeback accounting. The current codebase provides a FastAPI skeleton with in-memory state, basic governance validation, and a priority task queue — this spec captures what must be built to reach the AM-CP-v2.5 standard described in SPECIFICATION.md.

## Glossary

- **AgentMesh**: The Zuctro open-source control plane system described in this document.
- **Control Plane**: The central gateway service that receives, governs, queues, and routes agent tasks.
- **Task**: A unit of work submitted to the Control Plane, represented by `AgentTask` in `core/models.py`.
- **Worker Node**: An external agent runtime (Python, Node.js, Go, LangGraph, CrewAI, etc.) that polls the Control Plane for tasks and executes them.
- **Governance Policy**: A per-task configuration defining token budgets, financial caps, PII redaction settings, allowed tools, and HITL requirements.
- **HITL**: Human-in-the-Loop; a mechanism that pauses task execution waiting for a human operator decision.
- **PII**: Personally Identifiable Information; data such as emails, phone numbers, API keys, and credit card numbers.
- **DLQ**: Dead Letter Queue; the terminal failure state for tasks that exhaust all retries.
- **MCP**: Model Context Protocol; a standard protocol for agents to discover and call tools hosted on external servers.
- **OWASP LLM-01**: The OWASP Top 10 for LLM Applications risk category for prompt injection attacks.
- **Token Budget**: The maximum number of LLM tokens a task chain is allowed to consume.
- **Cost Center**: An enterprise accounting label (`cost_center`) used to attribute token and cost usage to a department.
- **Tenant**: An isolated organizational unit identified by `tenant_id`; each tenant has independent governance and resource usage.
- **OTel / OpenTelemetry**: The OpenTelemetry observability framework used for distributed tracing and metrics.
- **KEDA**: Kubernetes Event-Driven Autoscaling; scales worker pods based on queue depth metrics.
- **gVisor / Kata**: Sandbox container runtimes providing kernel-level isolation for worker pods.
- **SPIFFE**: Secure Production Identity Framework for Everyone; provides cryptographic workload identity.
- **Plugin**: A declarative YAML-configured governance or optimization module applied to the ingress pipeline.
- **AgentPluginBinding**: The Kubernetes CRD-style YAML object that binds plugins to agent pools.
- **AgentDeployment**: The Kubernetes CRD-style YAML object that defines worker pool scaling configuration.
- **Chargeback / Showback**: Financial accounting that attributes LLM token costs to tenants, cost centers, or departments.
- **Prompt Injection**: An attack vector (OWASP LLM-01) where adversarial text in a prompt attempts to override model instructions.
- **Semantic Cache**: A vector-similarity-based cache that returns previously computed LLM responses for near-duplicate prompts.
- **Failover**: Automatic re-routing of LLM requests from a failing primary provider to a secondary provider.
- **SSE**: Server-Sent Events; a unidirectional HTTP streaming protocol used for real-time task event streaming.
- **gRPC**: A high-performance RPC framework used for the AgentMesh protocol contract defined in `agentmesh.v2.proto`.

---

## Requirements

### Requirement 1: Task Submission and Governance Pipeline

**User Story:** As an enterprise AI engineer, I want to submit agent tasks through a governed ingress gateway, so that all tasks are validated, sanitized, and queued before execution begins.

#### Acceptance Criteria

1. WHEN a client submits a task via `POST /v1/tasks`, THE Control Plane SHALL validate the task against the active GovernancePolicy before enqueuing it.
2. WHEN PII redaction is enabled in the GovernancePolicy, THE Control Plane SHALL scan the task instruction and context fields for emails, phone numbers, API keys, and credit card numbers, replacing each match with a labeled redaction token (e.g., `[REDACTED_EMAIL]`) before the task enters the queue.
3. WHEN the token budget in the GovernancePolicy is zero or negative, THE Control Plane SHALL reject the task submission with an HTTP 422 response and a descriptive error message.
4. WHEN the financial cost cap in the GovernancePolicy is zero or negative, THE Control Plane SHALL reject the task submission with an HTTP 422 response and a descriptive error message.
5. WHEN a task passes all governance checks, THE Control Plane SHALL assign the task a unique `task_id`, set its status to `QUEUED`, persist it to the task store, and return the `task_id` in the HTTP 201 response.
6. WHEN a submitted task instruction contains a prompt injection pattern matching the configured sensitivity threshold, THE Control Plane SHALL block the task in `ENFORCE` mode or log and pass the task in `SHADOW` mode.

---

### Requirement 2: Priority Task Queue and Retry Engine

**User Story:** As a platform architect, I want tasks to be processed in priority order with automatic retry and dead-letter routing, so that high-priority work completes first and transient failures are recovered automatically.

#### Acceptance Criteria

1. THE Control Plane SHALL maintain a priority queue where tasks with higher numeric priority values are dequeued before tasks with lower values, and tasks with equal priority are ordered by submission time (FIFO).
2. WHEN a worker polls `POST /v1/workers/poll` with an `agent_type`, THE Control Plane SHALL dequeue and return the highest-priority task whose `agent_type` matches the worker's declared type or equals `general_worker`.
3. WHEN a worker submits a FAILED result and the task's retry count is below `max_retries`, THE Control Plane SHALL increment the retry counter, reset the task status to `QUEUED`, and re-enqueue the task.
4. WHEN a task's retry count reaches `max_retries` and the worker submits a FAILED result, THE Control Plane SHALL transition the task to `DEAD_LETTER_QUEUE` status and stop re-enqueuing it.
5. WHEN a task's cumulative token usage would exceed the `max_token_budget` governance limit, THE Control Plane SHALL transition the task to `DEAD_LETTER_QUEUE` status.
6. WHEN a task's cumulative cost would exceed the `max_cost_usd` governance limit, THE Control Plane SHALL transition the task to `DEAD_LETTER_QUEUE` status.

---

### Requirement 3: Human-in-the-Loop (HITL) Approval Gate

**User Story:** As a security governance director, I want high-risk agent tool calls to require human operator approval before execution, so that irreversible or destructive actions cannot be taken autonomously.

#### Acceptance Criteria

1. WHEN an agent worker requests execution of a tool listed in `require_hitl_for_tools`, THE Control Plane SHALL transition the task to `WAITING_HITL` status and halt further worker polling of that task.
2. WHEN a task is in `WAITING_HITL` status, THE Control Plane SHALL prevent the task from being dequeued or assigned to any worker until an operator decision is received.
3. WHEN an operator submits an APPROVED decision to `POST /v1/hitl/{task_id}/decision`, THE Control Plane SHALL transition the task back to `QUEUED` status and make it available for worker polling.
4. WHEN an operator submits a REJECTED decision to `POST /v1/hitl/{task_id}/decision`, THE Control Plane SHALL transition the task to `FAILED` status with the operator's rejection reason recorded in `error_message`.
5. WHEN a HITL task exceeds the configured `approvalTimeoutSeconds` without an operator decision, THE Control Plane SHALL transition the task to `FAILED` status with a timeout error message.

---

### Requirement 4: Model Context Protocol (MCP) Proxy Gateway

**User Story:** As an enterprise AI engineer, I want all agent MCP tool calls to be routed through a centralized proxy gateway, so that tool access is governed, logged, and sanitized before reaching upstream MCP servers.

#### Acceptance Criteria

1. WHEN an agent requests the tool list via `GET /v1/mcp/tools`, THE Control Plane SHALL return only the tools permitted by the requesting tenant's RBAC policy, filtering out any tools not in the tenant's allowlist.
2. WHEN an agent submits a tool call via `POST /v1/mcp/tools/call`, THE Control Plane SHALL apply PII redaction to all tool call arguments before forwarding the request to the upstream MCP server.
3. WHEN an agent submits a tool call for a tool listed in `require_hitl_for_tools`, THE Control Plane SHALL pause the tool call and transition the parent task to `WAITING_HITL` before forwarding to the upstream MCP server.
4. WHEN an MCP tool call is executed, THE Control Plane SHALL record the tool name, calling tenant, argument hashes, and response latency in the telemetry store.
5. THE Control Plane SHALL support MCP transport over HTTP with SSE in addition to standard HTTP request/response.

---

### Requirement 5: Telemetry, Observability, and Chargeback Engine

**User Story:** As an enterprise platform administrator, I want all task executions to generate structured telemetry data grouped by tenant and cost center, so that I can audit usage, enforce SLAs, and produce department-level chargeback reports.

#### Acceptance Criteria

1. WHEN a task completes or fails, THE Control Plane SHALL record prompt tokens, completion tokens, total cost in USD, execution time in milliseconds, and the number of tool calls in the task's `TelemetryMetrics` record.
2. WHEN token usage is recorded, THE Control Plane SHALL attribute the usage to the task's `tenant_id` and `cost_center` fields in the chargeback ledger.
3. THE Control Plane SHALL expose a `GET /v1/metrics/chargeback` endpoint that returns aggregated token counts and cost totals grouped by `tenant_id` and `cost_center` for a specified time range.
4. THE Control Plane SHALL expose a `GET /v1/metrics/summary` endpoint that returns current system-level counters including total tasks, queued tasks, active workers, total tokens burned, and total cost in USD.
5. WHEN a task transitions through any status change, THE Control Plane SHALL emit an OpenTelemetry span capturing the previous status, new status, task ID, tenant ID, and timestamp.
6. THE Control Plane SHALL serialize and deserialize all telemetry records to and from a persistent store using JSON encoding.

---

### Requirement 6: Worker Node Lifecycle Management

**User Story:** As a platform architect, I want the control plane to track worker registration, heartbeats, and idle/busy state, so that I can monitor fleet health and detect stale workers.

#### Acceptance Criteria

1. WHEN a worker polls for a task, THE Control Plane SHALL update that worker's `last_heartbeat` timestamp.
2. WHEN a worker is assigned a task, THE Control Plane SHALL update the worker's status to `BUSY` and record the `current_task_id`.
3. WHEN a worker submits a task result (COMPLETED or terminal FAILED/DLQ), THE Control Plane SHALL reset the worker's status to `IDLE` and clear `current_task_id`.
4. WHEN a worker has not sent a heartbeat within a configurable `worker_timeout_seconds` interval, THE Control Plane SHALL transition that worker's status to `OFFLINE`.
5. THE Control Plane SHALL expose a `GET /v1/workers` endpoint that returns the list of all registered workers with their current status, task counts, and last heartbeat timestamp.

---

### Requirement 7: Plugin System and Declarative Configuration

**User Story:** As a platform architect, I want governance and optimization rules to be configured as declarative YAML plugins applied at ingress, so that policies can be changed without code deployments.

#### Acceptance Criteria

1. THE Control Plane SHALL support a plugin pipeline with at minimum the following named plugins: `pii-redaction`, `prompt-injection-shield`, `token-budget-capper`, `mcp-tool-filter`, and `hitl-approval-router`.
2. WHEN a plugin configuration is loaded from a YAML `AgentPluginBinding` document, THE Control Plane SHALL apply that plugin's settings to all matching agent types on the next task submission without requiring a service restart.
3. WHEN the `prompt-injection-shield` plugin is set to `ENFORCE` mode and a prompt injection is detected, THE Control Plane SHALL reject the task with an HTTP 422 response.
4. WHEN the `prompt-injection-shield` plugin is set to `SHADOW` mode and a prompt injection is detected, THE Control Plane SHALL log the detection event and allow the task to proceed.
5. WHEN plugin configurations are serialized to and deserialized from YAML, THE Control Plane SHALL produce semantically equivalent plugin configurations (round-trip property).

---

### Requirement 8: Real-Time Task Event Streaming

**User Story:** As a developer integrating with AgentMesh, I want to stream real-time status updates for a specific task over SSE, so that I can build responsive UIs and downstream event handlers without polling.

#### Acceptance Criteria

1. WHEN a client connects to `GET /v1/tasks/{task_id}/stream`, THE Control Plane SHALL emit a Server-Sent Event for each status transition of that task until the task reaches a terminal state (`COMPLETED`, `FAILED`, or `DEAD_LETTER_QUEUE`).
2. WHEN a task reaches a terminal state, THE Control Plane SHALL emit a final SSE event and close the stream connection.
3. WHEN a client requests a stream for a non-existent `task_id`, THE Control Plane SHALL respond with HTTP 404.
4. WHEN a streamed event is emitted, THE Control Plane SHALL include the `task_id`, new `status`, `tenant_id`, current token counts, current cost in USD, and an ISO-8601 timestamp in the event payload.

---

### Requirement 9: API and Protocol Conformance

**User Story:** As an enterprise integrator, I want the Control Plane to conform to the AM-CP-v2.5 REST and gRPC protocol contracts, so that any compliant worker runtime can integrate without custom adapters.

#### Acceptance Criteria

1. THE Control Plane SHALL implement the REST endpoints `POST /v1/tasks`, `GET /v1/tasks/{task_id}`, `GET /v1/tasks`, `POST /v1/workers/poll`, `POST /v1/workers/submit-result`, `GET /v1/metrics/summary`, and `GET /v1/metrics/chargeback` as specified in the AM-CP-v2.5 standard.
2. THE Control Plane SHALL implement the gRPC service `AgentMeshControlPlane` with the methods `SubmitTask`, `PollTask`, `SubmitResult`, `SubmitHITLDecision`, and `StreamTaskEvents` as defined in `agentmesh.v2.proto`.
3. WHEN a `TaskEnvelope` is serialized over gRPC and then deserialized, THE Control Plane SHALL produce a `TaskEnvelope` that is semantically equivalent to the original (round-trip property).
4. WHEN the REST API returns a task object, THE Control Plane SHALL serialize the `AgentTask` to JSON using field names that match the `TaskEnvelope` protobuf field names for cross-protocol compatibility.
