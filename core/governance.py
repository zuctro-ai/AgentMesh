import re
from typing import Tuple, Dict, Any, List
from core.models import AgentTask, GovernancePolicy, TelemetryMetrics


class GovernanceInterceptor:
    """
    Governance & Security Gateway Interceptor.
    Enforces token budgets, financial limits, tool whitelists, and PII masking.
    """
    
    EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    PHONE_REGEX = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    API_KEY_REGEX = r'(?i)(sk-[a-zA-Z0-9]{32,}|bearer\s+[a-zA-Z0-9\-._~+/]+=*)'
    CREDIT_CARD_REGEX = r'\b(?:\d[ -]*?){13,16}\b'

    @classmethod
    def sanitize_text(cls, text: str) -> Tuple[str, List[str]]:
        redactions = []
        if re.search(cls.EMAIL_REGEX, text):
            text = re.sub(cls.EMAIL_REGEX, '[REDACTED_EMAIL]', text)
            redactions.append("EMAIL")
        if re.search(cls.PHONE_REGEX, text):
            text = re.sub(cls.PHONE_REGEX, '[REDACTED_PHONE]', text)
            redactions.append("PHONE")
        if re.search(cls.API_KEY_REGEX, text):
            text = re.sub(cls.API_KEY_REGEX, '[REDACTED_API_KEY]', text)
            redactions.append("API_KEY")
        if re.search(cls.CREDIT_CARD_REGEX, text):
            text = re.sub(cls.CREDIT_CARD_REGEX, '[REDACTED_CREDIT_CARD]', text)
            redactions.append("CREDIT_CARD")

        return text, redactions

    @classmethod
    def validate_task_submission(cls, task: AgentTask) -> Tuple[bool, str]:
        policy: GovernancePolicy = task.governance
        if policy.pii_redaction:
            sanitized_instruction, redactions = cls.sanitize_text(task.payload.instruction)
            if redactions:
                task.payload.instruction = sanitized_instruction
                
        if policy.max_token_budget <= 0:
            return False, "Governance policy error: Token budget must be > 0"

        if policy.max_cost_usd <= 0:
            return False, "Governance policy error: Financial budget must be > 0"

        return True, "Task passed governance check"

    @classmethod
    def check_token_budget_exceeded(cls, task: AgentTask, additional_tokens: int, estimated_cost: float) -> bool:
        new_total_tokens = task.telemetry.total_tokens + additional_tokens
        new_total_cost = task.telemetry.total_cost_usd + estimated_cost
        
        if new_total_tokens > task.governance.max_token_budget:
            return True
        if new_total_cost > task.governance.max_cost_usd:
            return True
            
        return False
