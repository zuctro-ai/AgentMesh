# AgentMesh: Open-Source Multi-Agent Control Plane & Governance Gateway

[![Specification](https://img.shields.io/badge/Specification-AM--CP--v1.0-blue.svg)](SPECIFICATION.md)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)

**AgentMesh** is an open-source, production-grade **Agent Control Plane** designed to solve multi-agent infrastructure challenges for enterprises. Just as **Kong** acts as an API Gateway and **Kubernetes** acts as a Container Orchestrator, AgentMesh acts as the **Control Plane for AI Agents**.

---

## 🌟 Key Capabilities

1. **SDK-Agnostic Execution Engine**: Orchestrate agents built in Python, TypeScript, Go, LangGraph, CrewAI, AutoGen, or custom scripts.
2. **Governance Interceptor**:
   - **Token Budget Accounting:** Cap token and dollar expenditures per task/tenant.
   - **Automatic PII Redaction:** Sanitizes emails, phone numbers, credit cards, and API keys before enqueuing.
   - **Tool Whitelisting & HITL:** Restrict tool access and trigger Human-in-the-Loop approval workflows.
3. **Queue & Fault Tolerance Engine**: Priority queueing, exponential backoff retries, sub-task delegation lineage, and Dead Letter Queues (DLQ).
4. **Real-Time Telemetry & Observability**: Token burn metrics, dollar cost tracking, and execution status monitoring.

---

## 📁 Repository Structure

```
AgentMesh/
├── SPECIFICATION.md       # AM-CP-v1.0 Formal Protocol Specification Standard
├── architecture_plan.md   # System Architecture & Topology Guide
├── app.py                 # Ingress API & REST Server (FastAPI)
├── core/
│   ├── models.py          # AM-CP-v1.0 Pydantic Data Contracts
│   ├── governance.py      # Governance Interceptor (PII & Token Budgets)
│   ├── database.py        # In-Memory & Telemetry Store
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
Refer to [SPECIFICATION.md](SPECIFICATION.md) to build compliant Control Plane Gateways or Worker Nodes in any language.

---

## 📄 Specification Standard

AgentMesh defines **AM-CP-v1.0 (AgentMesh Control Plane Protocol Specification v1.0)**. Any language runtime or framework can implement compliant worker nodes or control planes using our JSON data schemas and REST/SSE endpoints.

---

## 📜 License

Distributed under the Apache 2.0 License.
