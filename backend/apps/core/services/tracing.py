from apps.core.models import TraceLog


def trace_call(agent_name: str, arguments: dict, raw_response: str) -> TraceLog:
    """Record one LLM/agent call: what it was, what went in, what came back."""
    return TraceLog.objects.create(
        agent_name=agent_name,
        arguments=arguments,
        raw_response=raw_response,
    )
