"""
Zuctro AgentMesh - v3.0 Strategic Enterprise Roadmap Integration Test Suite
"""

import pytest
from fastapi.testclient import TestClient
from app import app
from core.auth import auth_manager
from core.hitl_bot import hitl_bot
from core.semantic_cache import semantic_cache
from core.model_router import smart_model_router
from core.eval_engine import eval_engine

client = TestClient(app)

def test_feature_1_enterprise_auth_rbac():
    # 1. Valid API Key
    user = auth_manager.authenticate_api_key("am_key_admin_secret_123")
    assert user.user_id == "admin_01"
    assert user.tenant_id == "admin_tenant"

    # 2. Scope authorization
    auth_manager.authorize_scope(user, "agentmesh:task:submit")

    # 3. Invalid API Key rejected
    with pytest.raises(Exception):
        auth_manager.authenticate_api_key("invalid_key_xyz")


def test_feature_2_hitl_bot_notification():
    card_slack = hitl_bot.build_slack_card("tsk_test_101", "execute_sql_mutation", "DROP TABLE users;", "tenant_a")
    assert "blocks" in card_slack
    assert "tsk_test_101" in card_slack["text"]

    card_teams = hitl_bot.build_teams_card("tsk_test_101", "execute_sql_mutation", "DROP TABLE users;", "tenant_a")
    assert card_teams["@type"] == "MessageCard"

    dispatched = hitl_bot.dispatch_hitl_notification("tsk_test_101", "execute_sql_mutation", "DROP TABLE users;", "tenant_a")
    assert dispatched is True


def test_feature_3_smart_model_router_and_semantic_cache():
    # Model router test: Simple vs Complex
    messages_simple = [{"role": "user", "content": "What is 2+2?"}]
    model_fast = smart_model_router.select_model("auto", messages_simple)
    assert model_fast == "gpt-4o-mini"

    messages_complex = [{"role": "user", "content": "Provide a distributed system design and security audit architecture for high throughput streaming."}]
    model_frontier = smart_model_router.select_model("auto", messages_complex)
    assert model_frontier == "gpt-4o"

    # Semantic Prompt Cache test
    semantic_cache.set(messages_simple, {"response": "4"})
    cached = semantic_cache.get(messages_simple)
    assert cached is not None
    assert cached["response"] == "4"


def test_feature_4_eval_engine():
    # Good output passed
    res_good = eval_engine.evaluate_output("Write python code", {"code": "def add(a,b): return a+b"})
    assert res_good.passed is True
    assert res_good.quality_score >= 0.70

    # Hallucinated output rejected
    res_bad = eval_engine.evaluate_output("Write python code", {"code": "fictional nonsensical output 999999"})
    assert res_bad.passed is False
    assert res_bad.hallucination_detected is True


def test_feature_5_governed_llm_proxy_with_auth_and_cache():
    headers = {"X-API-Key": "am_key_admin_secret_123"}
    payload = {
        "model": "auto",
        "messages": [{"role": "user", "content": "Explain microservices security in short."}]
    }

    # First call: cache miss
    resp1 = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["governance"]["semantic_cache_hit"] is False

    # Second call: cache hit
    resp2 = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["governance"]["semantic_cache_hit"] is True
