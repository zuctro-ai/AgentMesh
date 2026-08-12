import json
import pytest
from hypothesis import given, settings, strategies as st
from core.models import AgentTask, TaskPayload, GovernancePolicy, ChargebackRecord, AgentPluginBinding, PluginConfig
import agentmesh.v2_pb2 as agentmesh_v2_pb2



# **Feature: agentmesh-control-plane, Property 11: Task JSON Round-Trip**
@given(
    instruction=st.text(min_size=1, max_size=200),
    tenant_id=st.text(min_size=1, max_size=50),
    cost_center=st.text(min_size=1, max_size=50),
    max_tokens=st.integers(min_value=1, max_value=100000),
    max_cost=st.floats(min_value=0.01, max_value=100.0)
)
@settings(max_examples=100)
def test_task_json_round_trip(instruction, tenant_id, cost_center, max_tokens, max_cost):
    task = AgentTask(
        tenant_id=tenant_id,
        cost_center=cost_center,
        governance=GovernancePolicy(max_token_budget=max_tokens, max_cost_usd=max_cost),
        payload=TaskPayload(instruction=instruction, context={"key": "val"})
    )
    json_data = task.model_dump_json()
    deserialized = AgentTask.model_validate_json(json_data)
    assert deserialized.task_id == task.task_id
    assert deserialized.tenant_id == task.tenant_id
    assert deserialized.cost_center == task.cost_center
    assert deserialized.payload.instruction == task.payload.instruction


# **Feature: agentmesh-control-plane, Property 10: Plugin YAML Round-Trip**
def test_plugin_yaml_round_trip():
    binding = AgentPluginBinding(
        name="test-binding",
        target_agent_type="code_reviewer",
        plugins=[
            PluginConfig(name="pii-redaction", enabled=True, config={"redactTypes": ["EMAIL"]}),
            PluginConfig(name="prompt-injection-shield", enabled=True, config={"action": "ENFORCE"})
        ]
    )
    from core.plugins import plugin_engine
    yaml_str = f"""
apiVersion: agentmesh.io/v2alpha1
kind: AgentPluginBinding
metadata:
  name: {binding.name}
spec:
  targetAgentType: {binding.target_agent_type}
  plugins:
    - name: pii-redaction
      enabled: true
      config:
        redactTypes: ["EMAIL"]
    - name: prompt-injection-shield
      enabled: true
      config:
        action: ENFORCE
"""
    loaded = plugin_engine.load_binding(yaml_str)
    assert loaded.name == binding.name
    assert loaded.target_agent_type == binding.target_agent_type
    assert len(loaded.plugins) == 2


# **Feature: agentmesh-control-plane, Property 12: gRPC TaskEnvelope Round-Trip**
@given(
    instruction=st.text(min_size=1, max_size=100),
    tenant_id=st.text(min_size=1, max_size=30),
    priority=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100)
def test_grpc_task_envelope_round_trip(instruction, tenant_id, priority):
    envelope = agentmesh_v2_pb2.TaskEnvelope(
        task_id="tsk_test_123",
        tenant_id=tenant_id,
        cost_center="cc_engineering",
        agent_type="worker_a",
        priority=priority,
        status="PENDING",
        instruction=instruction,
        context_json=json.dumps({"env": "test"}),
        created_at=1770000000
    )
    serialized = envelope.SerializeToString()
    deserialized = agentmesh_v2_pb2.TaskEnvelope()
    deserialized.ParseFromString(serialized)

    assert deserialized.task_id == envelope.task_id
    assert deserialized.tenant_id == envelope.tenant_id
    assert deserialized.priority == envelope.priority
    assert deserialized.instruction == envelope.instruction
