import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_HITL = "WAITING_HITL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DLQ = "DEAD_LETTER_QUEUE"


class AgentStatus(str, Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"
    SPAWNING = "SPAWNING"


class GovernancePolicy(BaseModel):
    max_token_budget: int = Field(default=50000, description="Max total tokens allowed for this task chain")
    max_cost_usd: float = Field(default=0.50, description="Max financial budget in USD")
    allowed_tools: List[str] = Field(default_factory=list, description="Whitelist of tools agent is allowed to invoke")
    pii_redaction: bool = Field(default=True, description="Enable automatic PII masking in prompts & responses")
    require_hitl_for_tools: List[str] = Field(default_factory=list, description="Tools requiring human approval")


class TelemetryMetrics(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    tool_calls_count: int = 0
    execution_time_ms: float = 0.0


class TaskPayload(BaseModel):
    instruction: str
    context: Dict[str, Any] = Field(default_factory=dict)
    sub_tasks: List[str] = Field(default_factory=list)


class AgentTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"tsk_{uuid.uuid4().hex[:8]}")
    parent_task_id: Optional[str] = None
    tenant_id: str = "default_tenant"
    agent_type: str = "general_worker"
    assigned_worker_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 1  # 1 = Normal, 5 = High Priority
    retries: int = 0
    max_retries: int = 3
    
    governance: GovernancePolicy = Field(default_factory=GovernancePolicy)
    payload: TaskPayload
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    telemetry: TelemetryMetrics = Field(default_factory=TelemetryMetrics)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None


class WorkerInfo(BaseModel):
    worker_id: str = Field(default_factory=lambda: f"wrk_{uuid.uuid4().hex[:8]}")
    agent_type: str
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    tasks_completed: int = 0
    total_tokens_processed: int = 0
    last_heartbeat: float = Field(default_factory=time.time)
