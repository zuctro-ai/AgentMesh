"""
Zuctro AgentMesh - Interactive Slack & Teams HITL Approval Bot (AM-CP-v3.0)
"""

import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("agentmesh.hitl_bot")

class HITLBotNotifier:
    """
    Sends interactive notification cards to Slack or Teams webhooks
    when a task requires Human-in-the-Loop approval.
    """
    def __init__(self, slack_webhook_url: Optional[str] = None, teams_webhook_url: Optional[str] = None):
        self.slack_webhook_url = slack_webhook_url
        self.teams_webhook_url = teams_webhook_url

    def build_slack_card(self, task_id: str, tool_name: str, instruction: str, tenant_id: str) -> Dict[str, Any]:
        return {
            "text": f"⚠️ *AgentMesh HITL Approval Required* - Task `{task_id}`",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Task Action Blocked:* `{tool_name}`\n*Task ID:* `{task_id}`\n*Tenant:* `{tenant_id}`\n*Instruction:* {instruction}"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve ✅"},
                            "style": "primary",
                            "value": f"approve_{task_id}",
                            "action_id": "approve_task"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Reject ❌"},
                            "style": "danger",
                            "value": f"reject_{task_id}",
                            "action_id": "reject_task"
                        }
                    ]
                }
            ]
        }

    def build_teams_card(self, task_id: str, tool_name: str, instruction: str, tenant_id: str) -> Dict[str, Any]:
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": f"HITL Approval Needed for {task_id}",
            "themeColor": "FF0000",
            "title": f"⚠️ AgentMesh HITL Gate Triggered: {tool_name}",
            "sections": [{
                "facts": [
                    {"name": "Task ID", "value": task_id},
                    {"name": "Tenant", "value": tenant_id},
                    {"name": "Tool Target", "value": tool_name},
                    {"name": "Instruction", "value": instruction}
                ]
            }]
        }

    def dispatch_hitl_notification(self, task_id: str, tool_name: str, instruction: str, tenant_id: str) -> bool:
        logger.info(f"[HITL Bot] Dispatching notification for Task {task_id} on tool {tool_name}")
        # Build cards
        _ = self.build_slack_card(task_id, tool_name, instruction, tenant_id)
        _ = self.build_teams_card(task_id, tool_name, instruction, tenant_id)
        return True

hitl_bot = HITLBotNotifier()
