# Implementation Plan

- [x] 1. Extend core data models
  - Add `cost_center: str`, `hitl_trigger_tool: Optional[str]` fields to `AgentTask`
  - Add `AgentPluginBinding`, `PluginConfig` models for declarative plugin YAML config
  - Add `HITLDecision`, `ChargebackRecord`, `TaskEvent` models
  - Add `MCPTool`, `MCPToolCallRequest`, `MCPToolResult` models
  - _Requirements: 1.5, 3.3, 4.1, 5.2, 7.2, 8.4_

- [x] 1.1 Write property test for JSON round-trip on AgentTask and ChargebackRecord
  - **Property 11: Task JSON Round-Trip**
  - **Validates: Requirements 9.4, 5.6**

- [x] 2. Implement Plugin Engine (`core/plugins.py`)
  - [x] 2.1 Implement `BasePlugin` interface and `PluginResult` data class
  - [x] 2.2 Implement `PIIRedactionPlugin`
  - [x] 2.3 Write property test for PII redaction completeness
  - [x] 2.4 Implement `PromptInjectionShieldPlugin`
  - [x] 2.5 Write property test for injection shield enforce/shadow modes
  - [x] 2.6 Implement `TokenBudgetCapperPlugin` and `HITLApprovalRouterPlugin`
  - [x] 2.7 Write property test for budget boundary enforcement
  - [x] 2.8 Implement `MCPToolFilterPlugin`
  - [x] 2.9 Write property test for MCP tool filter allowlist restriction
  - [x] 2.10 Implement `PluginEngine.load_binding(yaml_str)` and `run_pipeline(task)`
  - [x] 2.11 Write property test for plugin YAML round-trip

- [x] 3. Extend Governance Interceptor (`core/governance.py`)
  - Add `check_prompt_injection(text, threshold) -> Tuple[bool, float]` method
  - Add `check_budget_on_result(task, tokens, cost) -> bool` method used post-result

- [x] 4. Extend Task Orchestrator (`core/orchestrator.py`)
  - [x] 4.1 Add `pause_task_for_hitl(task_id, tool_name) -> AgentTask`
  - [x] 4.2 Add `resume_task_from_hitl(task_id, decision, operator_id, reason) -> AgentTask`
  - [x] 4.3 Write property test for HITL state machine round-trip
  - [x] 4.4 Add per-task SSE event queue (`event_bus: Dict[str, asyncio.Queue]`)
  - [x] 4.5 Add background coroutine `expire_stale_hitl_tasks(timeout_seconds)`
  - [x] 4.6 Add background coroutine `expire_stale_workers(timeout_seconds)`
  - [x] 4.7 Write property test for priority queue ordering
  - [x] 4.8 Write property test for retry-to-DLQ lifecycle

- [x] 5. Extend Database Store (`core/database.py`)
  - Add `save_chargeback(record: ChargebackRecord)` and `get_chargeback_report(start_time) -> dict`
  - Add `save_worker`, `get_all_workers`, `update_worker_status` methods
  - [x] 5.1 Write property test for chargeback attribution consistency

- [x] 6. Implement MCP Proxy Gateway (`core/mcp_gateway.py`)
  - `MCPGateway.list_tools(tenant_id, rbac_policy)` — RBAC filtered tool list
  - `MCPGateway.call_tool(tenant_id, tool_name, arguments, pii_redact)` — proxied call with PII sanitization, audit logging

- [x] 7. Implement Telemetry Emitter (`core/telemetry.py`)
  - `OTelEmitter.emit_task_span(task, prev_status, new_status)` using `opentelemetry-sdk`
  - `OTelEmitter.emit_plugin_span(plugin_name, task_id, result)`

- [x] 8. Extend REST API (`app.py`)
  - [x] 8.1 Add `POST /v1/hitl/{task_id}/decision` endpoint
  - [x] 8.2 Add `GET /v1/tasks/{task_id}/stream` SSE endpoint
  - [x] 8.3 Write property test for SSE stream completeness
  - [x] 8.4 Add `GET /v1/mcp/tools` and `POST /v1/mcp/tools/call` endpoints
  - [x] 8.5 Add `GET /v1/workers` endpoint
  - [x] 8.6 Add `GET /v1/metrics/chargeback` endpoint
  - [x] 8.7 Wire plugin engine into `POST /v1/tasks` submission path

- [x] 9. Checkpoint — All core unit tests passing.

- [x] 10. Implement gRPC Service (`grpc_service/server.py`)
  - Implement `AgentMeshControlPlane` servicer from `agentmesh.v2.proto`
  - [x] 10.1 Write property test for gRPC TaskEnvelope round-trip

- [x] 11. Wire worker lifecycle updates into polling and result submission paths

- [x] 12. Enterprise Dashboard UI (`static/`)
  - Interactive web console for task submission, HITL operator approval gate, worker node status, and showback telemetry.

- [x] 13. Executable Global CLI Tool (`cli.py`, `setup.py`)
  - [x] 13.1 Implement standalone CLI binary for `agentmesh` status, task submit, list, inspect, stream, HITL approve/reject, and MCP listing.
  - [x] 13.2 Package setup entry point (`entry_points={'console_scripts': ['agentmesh=cli:main']}`).
  - [x] 13.3 Add unit test suite in `tests/test_cli.py`.

- [x] 14. Governed OpenAI-Compatible LLM Gateway Proxy (`POST /v1/chat/completions`)
  - [x] 14.1 Implement `POST /v1/chat/completions` proxy endpoint in `app.py`.
  - [x] 14.2 Enforce inline PII sanitization and OWASP prompt injection shield.
  - [x] 14.3 Record token usage and cost in financial chargeback ledger.

- [x] 15. Remote MCP Server Registration & Tool Sync (`core/mcp_gateway.py`)
  - [x] 15.1 Add `register_mcp_server` and `sync_remote_mcp_tools` JSON-RPC (`tools/list`) discovery.
  - [x] 15.2 Register default Jira & Confluence tool schemas.
  - [x] 15.3 Add `POST /v1/mcp/servers` and `POST /v1/mcp/servers/{server_name}/sync` API endpoints.

---

## 🚀 Zuctro AgentMesh v3.0 Strategic Enterprise Roadmap

- [x] 16. Enterprise Authentication & Multi-Tenant RBAC (Okta / Auth0 / Keycloak)
  - API Keys & Bearer JWT Validation: Secure all `/v1/tasks` and `/v1/mcp` endpoints.
  - Granular Scopes: Role-based permissions (`agentmesh:task:submit`, `agentmesh:hitl:approve`, `agentmesh:mcp:admin`).
  - Tenant Isolation: Hard cryptographic isolation ensuring Tenant A can never view or execute tasks/tools owned by Tenant B.

- [x] 17. Production Distributed Storage Backing (Redis & PostgreSQL)
  - Redis Queue & State Store: Replace the in-memory queue with Redis Streams / PubSub for zero-downtime control plane restarts and high-concurrency task dispatching.
  - PostgreSQL Audit Ledger: Durable long-term storage for task history, HITL decision logs, and FinOps financial chargeback records.

- [x] 18. Production Helm Chart & KEDA Kubernetes Auto-scaler CRD
  - Helm Chart (`charts/agentmesh`): Single-command deployment on Kubernetes (EKS, GKE, AKS).
  - KEDA ScaledObject Definition: Automatically scale worker agent pods from 0 to 100+ based on live Prometheus queue metrics (`agentmesh_queued_tasks > 0`).
  - Sandboxed Container Runtime: Run worker pods inside gVisor or Kata Containers for zero-trust sandbox isolation.

- [x] 19. Interactive Slack & Teams HITL Approval Bot
  - Real-Time Slack/Teams Notifications: When a task triggers an HITL hold state (e.g. `execute_sql_mutation`), AgentMesh sends an interactive message to a designated Slack/Teams channel.
  - One-Click Approval: Operators can click "Approve" or "Reject" directly inside Slack to resume or cancel the task without opening the dashboard.

- [x] 20. Semantic LLM Prompt Caching & Smart Model Router
  - Semantic Prompt Cache: Use vector similarity (Redis / Qdrant) to cache common agent sub-task responses, cutting LLM token costs by up to 80%.
  - Cost-Optimized Model Routing: Automatically route routine tasks to lightweight models (`gpt-4o-mini`, `llama-3.1-8b`) and route complex reasoning tasks to frontier models (`claude-3.5-sonnet`, `gpt-4o`).

- [x] 21. Real-Time LLM Quality & Hallucination Guardrails (Eval Engine)
  - Automated Quality Scoring: Score completed agent outputs for hallucinations, factual accuracy, and safety compliance before returning results to clients.
  - Automatic Failure Recovery: If hallucination score exceeds safety thresholds, automatically trigger a task retry or route to DLQ.


