import re
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from core.models import AgentTask, AgentPluginBinding, PluginConfig
from core.governance import GovernanceInterceptor


@dataclass
class PluginResult:
    allowed: bool = True
    modified_task: Optional[AgentTask] = None
    redactions: List[str] = field(default_factory=list)
    injection_score: float = 0.0
    audit_events: List[Dict[str, Any]] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    requires_hitl: bool = False
    hitl_trigger_tool: Optional[str] = None


class BasePlugin:
    name: str = "base"

    def execute(self, task: AgentTask, config: Dict[str, Any]) -> PluginResult:
        raise NotImplementedError


class PIIRedactionPlugin(BasePlugin):
    name = "pii-redaction"

    def execute(self, task: AgentTask, config: Dict[str, Any]) -> PluginResult:
        redact_types = config.get("redactTypes", ["EMAIL", "PHONE", "API_KEY", "CREDIT_CARD"])
        mask_replacement = config.get("maskReplacement", "[REDACTED]")

        all_redactions = []
        sanitized_instruction, redactions = GovernanceInterceptor.sanitize_text(task.payload.instruction)
        all_redactions.extend(redactions)
        task.payload.instruction = sanitized_instruction

        # Also sanitize context strings
        sanitized_context = {}
        for key, val in task.payload.context.items():
            if isinstance(val, str):
                s_val, r_val = GovernanceInterceptor.sanitize_text(val)
                sanitized_context[key] = s_val
                all_redactions.extend(r_val)
            else:
                sanitized_context[key] = val
        task.payload.context = sanitized_context

        unique_redactions = list(dict.fromkeys(all_redactions))
        audit = {
            "plugin": self.name,
            "redactions_count": len(unique_redactions),
            "types": unique_redactions
        }
        return PluginResult(allowed=True, modified_task=task, redactions=unique_redactions, audit_events=[audit])


class PromptInjectionShieldPlugin(BasePlugin):
    name = "prompt-injection-shield"

    INJECTION_PATTERNS = [
        r'(?i)ignore\s+previous\s+instructions',
        r'(?i)disregard\s+system\s+prompt',
        r'(?i)jailbreak',
        r'(?i)override\s+safety\s+policy',
        r'(?i)bypass\s+security\s+filter',
        r'(?i)developer\s+mode\s+enabled',
        r'(?i)sudo\s+execute',
        r'(?i)you\s+are\s+now\s+unrestricted',
        r'(?i)forget\s+all\s+prior\s+rules'
    ]

    def _calculate_score(self, text: str) -> float:
        score = 0.0
        matches = 0
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, text):
                matches += 1

        if matches == 1:
            score = 0.88
        elif matches > 1:
            score = 0.98
        return score

    def execute(self, task: AgentTask, config: Dict[str, Any]) -> PluginResult:
        action = config.get("action", "ENFORCE").upper()  # ENFORCE or SHADOW
        threshold = config.get("sensitivityThreshold", 0.85)

        full_text = f"{task.payload.instruction} {task.payload.context}"
        score = self._calculate_score(full_text)

        audit = {
            "plugin": self.name,
            "injection_score": score,
            "threshold": threshold,
            "action": action
        }

        if score >= threshold:
            if action == "ENFORCE":
                return PluginResult(
                    allowed=False,
                    modified_task=task,
                    injection_score=score,
                    audit_events=[audit],
                    rejection_reason=f"Prompt injection detected (score: {score:.2f} >= threshold: {threshold})"
                )
            else:
                # SHADOW mode: log audit but allow
                audit["shadow_blocked"] = True
                return PluginResult(
                    allowed=True,
                    modified_task=task,
                    injection_score=score,
                    audit_events=[audit]
                )

        return PluginResult(allowed=True, modified_task=task, injection_score=score, audit_events=[audit])


class TokenBudgetCapperPlugin(BasePlugin):
    name = "token-budget-capper"

    def execute(self, task: AgentTask, config: Dict[str, Any]) -> PluginResult:
        max_tokens = config.get("maxTokensPerTaskChain", task.governance.max_token_budget)
        max_cost = config.get("maxCostUsdPerTaskChain", task.governance.max_cost_usd)

        audit = {
            "plugin": self.name,
            "max_tokens": max_tokens,
            "max_cost": max_cost
        }

        if max_tokens <= 0:
            return PluginResult(
                allowed=False,
                modified_task=task,
                audit_events=[audit],
                rejection_reason="Governance policy error: Token budget must be > 0"
            )

        if max_cost <= 0:
            return PluginResult(
                allowed=False,
                modified_task=task,
                audit_events=[audit],
                rejection_reason="Governance policy error: Financial budget must be > 0"
            )

        return PluginResult(allowed=True, modified_task=task, audit_events=[audit])


class HITLApprovalRouterPlugin(BasePlugin):
    name = "hitl-approval-router"

    def execute(self, task: AgentTask, config: Dict[str, Any]) -> PluginResult:
        require_tools = config.get("requireHitlTools", [])
        combined_tools = set(require_tools + task.governance.require_hitl_for_tools)

        text_to_check = f"{task.payload.instruction} {task.payload.context}".lower()

        matched_tool = None
        for tool in combined_tools:
            if tool.lower() in text_to_check:
                matched_tool = tool
                break

        audit = {
            "plugin": self.name,
            "hitl_triggered": matched_tool is not None,
            "matched_tool": matched_tool
        }

        if matched_tool:
            return PluginResult(
                allowed=True,
                modified_task=task,
                requires_hitl=True,
                hitl_trigger_tool=matched_tool,
                audit_events=[audit]
            )

        return PluginResult(allowed=True, modified_task=task, audit_events=[audit])


class MCPToolFilterPlugin(BasePlugin):
    name = "mcp-tool-filter"

    def execute(self, task: AgentTask, config: Dict[str, Any]) -> PluginResult:
        allowlist = config.get("allowlist", [])
        audit = {
            "plugin": self.name,
            "allowlist": allowlist
        }
        return PluginResult(allowed=True, modified_task=task, audit_events=[audit])


class PluginEngine:
    def __init__(self):
        self.registry: Dict[str, BasePlugin] = {}
        self.register_plugin(PIIRedactionPlugin())
        self.register_plugin(PromptInjectionShieldPlugin())
        self.register_plugin(TokenBudgetCapperPlugin())
        self.register_plugin(HITLApprovalRouterPlugin())
        self.register_plugin(MCPToolFilterPlugin())
        self.bindings: Dict[str, AgentPluginBinding] = {}

    def register_plugin(self, plugin: BasePlugin):
        self.registry[plugin.name] = plugin

    def load_binding(self, yaml_str: str) -> AgentPluginBinding:
        data = yaml.safe_load(yaml_str)
        if isinstance(data, dict) and "spec" in data:
            spec = data["spec"]
            plugins_data = spec.get("plugins", [])
            plugin_configs = []
            for p in plugins_data:
                plugin_configs.append(PluginConfig(
                    name=p.get("name"),
                    enabled=p.get("enabled", True),
                    config=p.get("config", {})
                ))
            binding = AgentPluginBinding(
                name=data.get("metadata", {}).get("name", "default-binding"),
                target_agent_type=spec.get("targetAgentType", "*"),
                plugins=plugin_configs
            )
        elif isinstance(data, dict) and "name" in data:
            binding = AgentPluginBinding(**data)
        else:
            raise ValueError("Invalid plugin binding format")

        self.bindings[binding.name] = binding
        return binding

    def run_pipeline(self, task: AgentTask, binding: Optional[AgentPluginBinding] = None) -> PluginResult:
        cumulative_redactions = []
        cumulative_audit = []
        max_injection_score = 0.0
        requires_hitl = False
        hitl_trigger_tool = None
        current_task = task

        plugins_to_run: List[Tuple[BasePlugin, Dict[str, Any]]] = []

        if binding:
            for p_cfg in binding.plugins:
                if p_cfg.enabled and p_cfg.name in self.registry:
                    plugins_to_run.append((self.registry[p_cfg.name], p_cfg.config))
        else:
            # Default pipeline execution
            plugins_to_run = [
                (self.registry["pii-redaction"], {}),
                (self.registry["prompt-injection-shield"], {}),
                (self.registry["token-budget-capper"], {}),
                (self.registry["hitl-approval-router"], {})
            ]

        for plugin, config in plugins_to_run:
            res = plugin.execute(current_task, config)
            if res.modified_task:
                current_task = res.modified_task
            cumulative_redactions.extend(res.redactions)
            cumulative_audit.extend(res.audit_events)
            if res.injection_score > max_injection_score:
                max_injection_score = res.injection_score
            if res.requires_hitl:
                requires_hitl = True
                hitl_trigger_tool = res.hitl_trigger_tool

            if not res.allowed:
                return PluginResult(
                    allowed=False,
                    modified_task=current_task,
                    redactions=list(dict.fromkeys(cumulative_redactions)),
                    injection_score=max_injection_score,
                    audit_events=cumulative_audit,
                    rejection_reason=res.rejection_reason
                )

        return PluginResult(
            allowed=True,
            modified_task=current_task,
            redactions=list(dict.fromkeys(cumulative_redactions)),
            injection_score=max_injection_score,
            audit_events=cumulative_audit,
            requires_hitl=requires_hitl,
            hitl_trigger_tool=hitl_trigger_tool
        )


plugin_engine = PluginEngine()
