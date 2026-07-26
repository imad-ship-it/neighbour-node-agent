from apps.core.models import TraceLog


def trace_call(
    agent_name: str,
    arguments: dict,
    raw_response: str = "",
    *,
    run_id: str = "",
    step_index: int = 0,
    tool_name: str = "",
    duration_ms: int | None = None,
    status: str = "ok",
) -> TraceLog:
    """Record one tool/LLM call within an agent run.

    Extraction is a single call; a match agent is a graph of them. `run_id`
    ties the steps of one run together, `step_index` orders them, and
    `tool_name`/`duration_ms`/`status` describe each step — this is the trace
    you show on screen during the multi-step demo.
    """
    return TraceLog.objects.create(
        agent_name=agent_name,
        arguments=arguments,
        raw_response=raw_response,
        run_id=run_id,
        step_index=step_index,
        tool_name=tool_name,
        duration_ms=duration_ms,
        status=status,
    )
