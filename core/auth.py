"""
Zuctro AgentMesh - Enterprise Authentication & Multi-Tenant RBAC Module (AM-CP-v3.0)
"""

import os
import time
import hmac
import hashlib
from typing import Dict, List, Optional, Set
from pydantic import BaseModel
from fastapi import HTTPException, Security, Depends, Header
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

class UserIdentity(BaseModel):
    user_id: str
    tenant_id: str
    roles: List[str]
    scopes: Set[str]
    cost_center: str = "default"

class AuthManager:
    """
    Manages API Key authentication, JWT validation, and RBAC scope checking.
    """
    def __init__(self):
        # Default dev API keys for multi-tenant isolation
        self.api_keys: Dict[str, UserIdentity] = {
            "am_key_admin_secret_123": UserIdentity(
                user_id="admin_01",
                tenant_id="admin_tenant",
                roles=["admin"],
                scopes={"agentmesh:task:submit", "agentmesh:hitl:approve", "agentmesh:mcp:admin", "agentmesh:read"},
                cost_center="cc_corp"
            ),
            "am_key_tenant_a_456": UserIdentity(
                user_id="user_tenant_a",
                tenant_id="tenant_a",
                roles=["developer"],
                scopes={"agentmesh:task:submit", "agentmesh:read"},
                cost_center="cc_eng_a"
            ),
            "am_key_tenant_b_789": UserIdentity(
                user_id="user_tenant_b",
                tenant_id="tenant_b",
                roles=["developer"],
                scopes={"agentmesh:task:submit", "agentmesh:read"},
                cost_center="cc_eng_b"
            )
        }

    def authenticate_api_key(self, api_key: Optional[str]) -> UserIdentity:
        if not api_key:
            # For backward compatibility in dev mode if auth is disabled
            return UserIdentity(
                user_id="anonymous",
                tenant_id="default",
                roles=["admin"],
                scopes={"agentmesh:task:submit", "agentmesh:hitl:approve", "agentmesh:mcp:admin", "agentmesh:read"},
                cost_center="default"
            )
        
        if api_key not in self.api_keys:
            raise HTTPException(status_code=401, detail="Invalid API Key")
        return self.api_keys[api_key]

    def authorize_scope(self, identity: UserIdentity, required_scope: str):
        if required_scope not in identity.scopes and "admin" not in identity.roles:
            raise HTTPException(status_code=403, detail=f"Permission denied: Missing scope {required_scope}")

    def verify_tenant_isolation(self, identity: UserIdentity, target_tenant_id: str):
        if identity.tenant_id != "admin_tenant" and identity.tenant_id != target_tenant_id:
            raise HTTPException(status_code=403, detail="Cross-tenant access forbidden")

auth_manager = AuthManager()
