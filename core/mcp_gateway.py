import requests
from typing import Dict, List, Optional, Any
from core.models import MCPTool, MCPToolCallRequest, MCPToolResult
from core.governance import GovernanceInterceptor


class MCPServerConfig:
    def __init__(self, name: str, endpoint_url: str, auth_token: Optional[str] = None):
        self.name = name
        self.endpoint_url = endpoint_url
        self.auth_token = auth_token


class MCPGateway:
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.tenant_allowlists: Dict[str, List[str]] = {}
        self.remote_mcp_servers: Dict[str, MCPServerConfig] = {}
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
            ),
            MCPTool(
                name="jira_get_issue",
                description="Fetch Jira ticket details by issue key (e.g. PROJ-102)",
                parameters_schema={"type": "object", "properties": {"issue_key": {"type": "string"}}},
                required_rbac_role="developer"
            ),
            MCPTool(
                name="jira_create_issue",
                description="Create a new Jira issue ticket",
                parameters_schema={"type": "object", "properties": {"project_key": {"type": "string"}, "summary": {"type": "string"}, "description": {"type": "string"}}},
                required_rbac_role="developer"
            ),
            MCPTool(
                name="confluence_get_page",
                description="Fetch page title and content from Confluence documentation workspace",
                parameters_schema={"type": "object", "properties": {"space_key": {"type": "string"}, "title": {"type": "string"}}},
                required_rbac_role="developer"
            ),
            MCPTool(
                name="confluence_search_pages",
                description="Search Confluence pages using CQL query",
                parameters_schema={"type": "object", "properties": {"cql": {"type": "string"}}},
                required_rbac_role="developer"
            )
        ]

        for tool in default_tools:
            self.register_tool(tool)

    def register_tool(self, tool: MCPTool):
        self.tools[tool.name] = tool

    def register_mcp_server(self, name: str, endpoint_url: str, auth_token: Optional[str] = None):
        """Register an external Model Context Protocol (MCP) server endpoint."""
        self.remote_mcp_servers[name] = MCPServerConfig(name, endpoint_url, auth_token)

    def sync_remote_mcp_tools(self, server_name: str) -> List[MCPTool]:
        """Discover tools from an external standard MCP server (via tools/list JSON-RPC)."""
        if server_name not in self.remote_mcp_servers:
            return []

        server = self.remote_mcp_servers[server_name]
        headers = {"Content-Type": "application/json"}
        if server.auth_token:
            headers["Authorization"] = f"Bearer {server.auth_token}"

        json_rpc_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 1
        }

        try:
            res = requests.post(server.endpoint_url, json=json_rpc_payload, headers=headers, timeout=5.0)
            if res.status_code == 200:
                data = res.json()
                discovered = []
                tools_list = data.get("result", {}).get("tools", [])
                for t in tools_list:
                    tool = MCPTool(
                        name=t.get("name"),
                        description=t.get("description", ""),
                        parameters_schema=t.get("inputSchema", {})
                    )
                    self.register_tool(tool)
                    discovered.append(tool)
                return discovered
        except Exception as e:
            print(f"Failed to sync remote MCP server {server_name}: {e}")

        return []

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
                error_message=f"Tool '{request.tool_name}' not found in MCP registry"
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
                "message": f"Successfully executed MCP tool '{request.tool_name}'"
            },
            redactions=list(dict.fromkeys(all_redactions))
        )


mcp_gateway = MCPGateway()
