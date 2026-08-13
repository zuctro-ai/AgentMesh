# 🛡️ Zuctro AgentMesh: Open-Source Multi-Agent Control Plane & Governance Gateway

[![Specification](https://img.shields.io/badge/Specification-AM--CP--v2.5-blue.svg)](SPECIFICATION.md)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Company](https://img.shields.io/badge/Company-Zuctro_AI-purple.svg)](https://zuctro.ai)

**Zuctro AgentMesh** is an open-source, production-grade **Agent Control Plane & Gateway** designed to solve multi-agent infrastructure challenges for enterprises. AgentMesh acts as the Enterprise Gateway, Security Interceptor, and Kubernetes Pod Orchestrator for AI Agents.

---

## 🌟 Key Capabilities

1. **Declarative Plugin Architecture:** Reusable YAML plugins for PII sanitization, OWASP prompt injection shields, token budget capping, and HITL approval routing.
2. **Model Context Protocol (MCP) Proxy Gateway:** Centralized proxying, tool discovery filtering (`tools/list`), parameter sanitization, and HITL authorization for MCP tool calls (`tools/call`).
3. **Kubernetes Scale-to-Zero Pod Execution:** Dynamic worker pod lifecycle managed via KEDA based on queue depth metrics (`agentmesh_queued_tasks > 0`) with container sandbox isolation (`gVisor` / `Kata`).
4. **gRPC & REST Dual Protocol Support:** Full parity between REST/SSE (`app.py`) and high-performance gRPC service (`agentmesh.v2.proto`).
5. **SDK-Agnostic Worker Runtimes:** Orchestrate agents built in Python, TypeScript, Go, LangGraph, CrewAI, AutoGen, or custom scripts.
6. **Real-Time Telemetry & Observability:** OpenTelemetry GenAI trace DAGs, Prometheus metrics, and enterprise showback/chargeback accounting.

---

## 📁 Repository Structure

```
AgentMesh/
├── SPECIFICATION.md       # Zuctro AM-CP-v2.5 Enterprise Protocol Specification
├── architecture_plan.md   # System Architecture & Topology Guide
├── app.py                 # Ingress REST API & SSE Streaming Gateway (FastAPI)
├── core/
│   ├── models.py          # AM-CP Data Contracts (Pydantic)
│   ├── plugins.py         # Declarative Plugin Interceptor Pipeline & Engine
│   ├── governance.py      # Governance Interceptor (PII & Token Budgets)
│   ├── database.py        # State Store & Chargeback Accounting Ledger
│   ├── orchestrator.py    # Async Priority Task Queue, HITL Pauser & DLQ Engine
│   ├── mcp_gateway.py     # Model Context Protocol (MCP) Proxy Gateway
│   └── telemetry.py       # OpenTelemetry AI Span Emitter
├── proto/
│   └── agentmesh.v2.proto # gRPC Protocol Contract
├── grpc_service/
│   └── server.py          # gRPC Server Implementation
├── tests/                 # Unit, Property, and AM-CP-v2.5 Conformance Suite
│   ├── test_models.py
│   ├── test_plugins.py
│   ├── test_governance.py
│   ├── test_orchestrator.py
│   ├── test_api.py
│   ├── test_grpc.py
│   └── test_conformance.py
└── README.md              # Project Overview
```

---

## 🚀 Quickstart

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn pydantic pyyaml hypothesis pytest httpx opentelemetry-api opentelemetry-sdk grpcio grpcio-tools pytest-asyncio
```

### 2. Install global `agentmesh` CLI command

```bash
pip install -e .
```

### 3. Launch the REST & SSE Control Plane Gateway & UI

```bash
uvicorn app:app --reload --port 8000
```

Access the UI Dashboard at `http://localhost:8000/`, interactive API documentation at `http://localhost:8000/docs`, and Prometheus metrics at `http://localhost:8000/metrics`.

### 4. Use the `agentmesh` Command Line Tool

```bash
# Check control plane status & metrics
agentmesh status

# Submit a task instruction
agentmesh task submit -i "Scrub PII and analyze ticket JIRA-102" --agent-type data_analyst --follow

# List tasks or inspect a task
agentmesh task list
agentmesh task inspect tsk_55436075

# Manage Human-in-the-Loop (HITL) approval gate
agentmesh hitl list
agentmesh hitl approve tsk_af2bd402

# List registered MCP tools
agentmesh mcp list
```

### 5. Run the AM-CP-v2.5 Conformance & Test Suite

```bash
PYTHONPATH=. pytest -v
```


---

## 📄 Specification Standard

Zuctro AgentMesh defines **AM-CP-v2.5** (Control Plane Specification) and **AM-MCP-v1.0** (Model Context Protocol Gateway). Any language runtime or framework can implement compliant worker nodes or control planes using our JSON/gRPC contracts.

---

## 📜 License

Distributed under the Apache 2.0 License. © [Zuctro AI](https://zuctro.ai)
