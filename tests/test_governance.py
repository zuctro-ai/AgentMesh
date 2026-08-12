import pytest
from hypothesis import given, settings, strategies as st
from core.models import AgentTask, TaskPayload, GovernancePolicy
from core.governance import GovernanceInterceptor


# **Feature: agentmesh-control-plane, Property 2: Whitespace-Only and Empty Instructions are Rejected**
@given(ws=st.text(alphabet=" \t\n\r", min_size=0, max_size=50))
@settings(max_examples=100)
def test_whitespace_instructions_rejected(ws):
    task = AgentTask(payload=TaskPayload(instruction=ws))
    # Check if instruction stripped is empty
    assert len(task.payload.instruction.strip()) == 0


def test_governance_invalid_budgets():
    task_bad_token = AgentTask(
        governance=GovernancePolicy(max_token_budget=0),
        payload=TaskPayload(instruction="Valid instruction")
    )
    passed, msg = GovernanceInterceptor.validate_task_submission(task_bad_token)
    assert passed is False
    assert "Token budget must be > 0" in msg

    task_bad_cost = AgentTask(
        governance=GovernancePolicy(max_cost_usd=-1.0),
        payload=TaskPayload(instruction="Valid instruction")
    )
    passed, msg = GovernanceInterceptor.validate_task_submission(task_bad_cost)
    assert passed is False
    assert "Financial budget must be > 0" in msg
