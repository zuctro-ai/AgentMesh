from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from core.models import AgentTask, TaskStatus


class OTelEmitter:
    def __init__(self):
        try:
            provider = TracerProvider()
            processor = BatchSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)
        except Exception:
            pass
        self.tracer = trace.get_tracer("agentmesh.control_plane", "2.5.0")

    def emit_task_span(self, task: AgentTask, prev_status: TaskStatus, new_status: TaskStatus):
        with self.tracer.start_as_current_span(f"task.{new_status.value.lower()}") as span:
            span.set_attribute("task.id", task.task_id)
            span.set_attribute("task.tenant_id", task.tenant_id)
            span.set_attribute("task.cost_center", task.cost_center)
            span.set_attribute("task.agent_type", task.agent_type)
            span.set_attribute("task.prev_status", prev_status.value)
            span.set_attribute("task.new_status", new_status.value)
            span.set_attribute("task.prompt_tokens", task.telemetry.prompt_tokens)
            span.set_attribute("task.completion_tokens", task.telemetry.completion_tokens)
            span.set_attribute("task.total_cost_usd", task.telemetry.total_cost_usd)

    def emit_plugin_span(self, plugin_name: str, task_id: str, allowed: bool, score: float = 0.0):
        with self.tracer.start_as_current_span(f"plugin.{plugin_name}") as span:
            span.set_attribute("plugin.name", plugin_name)
            span.set_attribute("task.id", task_id)
            span.set_attribute("plugin.allowed", allowed)
            span.set_attribute("plugin.score", score)


otel_emitter = OTelEmitter()
