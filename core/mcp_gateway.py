from typing import Dict, List, Optional, Any
from core.models import MCPTool, MCPToolCallRequest, MCPToolResult
from core.governance import GovernanceInterceptor


class MCPGateway:
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.tenant_allowlists: Dict[str, List[str]] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        default_tools = [
            MCPTool(
                name="execute_sql_mutation",
                description="Execute SQL mutation query against database",
                parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                required_rbac_role="db_admin"
            ),
            MCPTool(
                name="git_push_production",
                description="Push Git commit to production release branch",
                parameters_schema={"type": "object", "properties": {"branch": {"type": "string"}, "commit_sha": {"type": "string"}}},
                required_rbac_role="lead_engineer"
            ),
            MCPTool(
                name="deploy_cloud_infrastructure",
                description="Deploy cloud infrastructure stack",
                parameters_schema={"type": "object", "properties": {"stack_name": {"type": "string"}}},
                required_rbac_role="cloud_admin"
            ),
            MCPTool(
                name="query_db",
                description="Execute read-only SQL query",
                parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                required_rbac_role="analyst"
            )
        ]
        for tool in default_tools:
            self.register_tool(tool)

    def register_tool(self, tool: MCPTool):
        self.tools[tool.name] = tool

    def set_tenant_allowlist(self, tenant_id: str, allowlist: List[str]):
        self.tenant_allowlists[tenant_id] = allowlist

    def list_tools(self, tenant_id: str = "default_tenant", user_role: Optional[str] = None) -> List[MCPTool]:
        available = list(self.tools.values())

        if tenant_id in self.tenant_allowlists:
            allowed_names = set(self.tenant_allowlists[tenant_id])
            available = [t for t in available if t.name in allowed_names]

        if user_role:
            available = [t for t in available if not t.required_rbac_role or t.required_rbac_role == user_role]

        return available

    def call_tool(self, request: MCPToolCallRequest) -> MCPToolResult:
        if request.tool_name not in self.tools:
            return MCPToolResult(
                tool_name=request.tool_name,
                success=False,
                error_message=f"Tool {request.tool_name} not found in MCP registry"
            )

        sanitized_args = {}
        all_redactions = []

        for key, val in request.arguments.items():
            if isinstance(val, str) and request.pii_redact:
                s_val, r_list = GovernanceInterceptor.sanitize_text(val)
                sanitized_args[key] = s_val
                all_redactions.extend(r_list)
            else:
                sanitized_args[key] = val

        return MCPToolResult(
            tool_name=request.tool_name,
            success=True,
            result_data={
                "status": "EXECUTED",
                "arguments": sanitized_args,
                "message": f"Successfully executed MCP tool {request.tool_name}"
            },
            redactions=list(dict.fromkeys(all_redactions))
        )


mcp_gateway = MCPGateway()
