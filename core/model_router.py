"""
Zuctro AgentMesh - Smart Cost-Optimized Model Router (AM-CP-v3.0)
"""

from typing import Dict, Any

class SmartModelRouter:
    """
    Analyzes prompt complexity and routes routine queries to lightweight models (e.g. gpt-4o-mini)
    and complex reasoning queries to frontier models (e.g. claude-3.5-sonnet, gpt-4o).
    """
    def __init__(self):
        self.complex_keywords = {"architecture", "security audit", "refactor", "mathematical proof", "policy compliance", "distributed system design"}
        self.fast_model = "gpt-4o-mini"
        self.frontier_model = "gpt-4o"

    def select_model(self, requested_model: str, messages: list) -> str:
        prompt_text = " ".join([m.get("content", "") for m in messages if isinstance(m, dict)]).lower()
        
        # If user explicitly specified a non-default model, respect requested_model
        if requested_model and requested_model not in ["auto", "default"]:
            return requested_model

        # Keyword / complexity heuristic
        words = prompt_text.split()
        if len(words) > 300 or any(kw in prompt_text for kw in self.complex_keywords):
            return self.frontier_model
        return self.fast_model

smart_model_router = SmartModelRouter()
