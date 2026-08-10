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
4. **SDK-Agnostic Worker Runtimes:** Orchestrate agents built in Python, TypeScript, Go, LangGraph, CrewAI, AutoGen, or custom scripts.
5. **Real-Time Telemetry & Observability:** OpenTelemetry GenAI trace DAGs, Prometheus metrics, and enterprise showback/chargeback accounting.

---

## 📁 Repository Structure

```
AgentMesh/
├── SPECIFICATION.md       # Zuctro AM-CP-v2.5 Enterprise Protocol Specification
├── architecture_plan.md   # System Architecture & Topology Guide
├── app.py                 # Ingress API & REST Server (FastAPI)
├── core/
│   ├── models.py          # AM-CP Data Contracts (Pydantic)
│   ├── governance.py      # Governance Interceptor (PII & Token Budgets)
│   ├── database.py        # Telemetry & State Store
│   └── orchestrator.py    # Async Priority Task Queue & DLQ Engine
└── README.md              # Project Overview
```

---

## 🚀 Quickstart

### 1. Install Dependencies

```bash
pip install fastapi uvicorn pydantic
```

### 2. Launch the Control Plane Gateway

```bash
uvicorn app:app --reload --port 8000
```

Access the interactive API documentation at `http://localhost:8000/docs`.

### 3. Read the Protocol Specification Standard

Refer to [SPECIFICATION.md](SPECIFICATION.md) to implement compliant Control Plane Gateways or Worker Nodes in any language.

---

## 📄 Specification Standard

Zuctro AgentMesh defines **AM-CP-v2.5** (Control Plane Specification) and **AM-MCP-v1.0** (Model Context Protocol Gateway). Any language runtime or framework can implement compliant worker nodes or control planes using our JSON/gRPC contracts.

---

## 📜 License

Distributed under the Apache 2.0 License. © [Zuctro AI](https://zuctro.ai)
