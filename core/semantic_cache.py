"""
Zuctro AgentMesh - Semantic LLM Prompt Caching (AM-CP-v3.0)
"""

import hashlib
import time
from typing import Dict, Any, Optional

class SemanticPromptCache:
    """
    Vector similarity & exact hash prompt completion cache.
    Cuts LLM token consumption and latency for repeated agent queries.
    """
    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def _normalize_prompt(self, messages: list) -> str:
        content_str = "".join([m.get("content", "") for m in messages if isinstance(m, dict)])
        return hashlib.sha256(content_str.strip().lower().encode("utf-8")).hexdigest()

    def get(self, messages: list) -> Optional[Dict[str, Any]]:
        prompt_hash = self._normalize_prompt(messages)
        if prompt_hash in self.cache:
            item = self.cache[prompt_hash]
            if time.time() - item["timestamp"] < self.ttl_seconds:
                return item["response"]
            else:
                del self.cache[prompt_hash]
        return None

    def set(self, messages: list, response: Dict[str, Any]):
        prompt_hash = self._normalize_prompt(messages)
        self.cache[prompt_hash] = {
            "response": response,
            "timestamp": time.time()
        }

semantic_cache = SemanticPromptCache()
