"""Build a TraceRun tree from a flat list of LangChain messages."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from trace.schema import TraceRun


def _uid() -> str:
    return str(uuid.uuid4())


def _extract_tokens(msg) -> dict:
    """Pull token counts from a LangChain message's response_metadata."""
    metadata = getattr(msg, "response_metadata", {})
    usage = metadata.get("token_usage", {})
    return {
        "input": usage.get("prompt_tokens", 0),
        "output": usage.get("completion_tokens", 0),
    }


def _token_total(tokens: dict) -> int:
    return tokens.get("input", 0) + tokens.get("output", 0)


def _safe_str(value) -> str:
    """Coerce a value to a JSON-safe string, truncating if very long."""
    if value is None:
        return ""
    s = str(value)
    if len(s) > 4000:
        return s[:4000] + f"... [truncated, {len(s)} chars]"
    return s


def _truncate_content(content: str, limit: int = 4000) -> str:
    if content and len(content) > limit:
        return content[:limit] + f"... [truncated, {len(content)} chars]"
    return content or ""


def _build_tool_call_run(
    tool_call: dict,
    result_msg,
    parent_id: str,
) -> TraceRun:
    """Create a TraceRun for a single tool call + its result."""
    tool_name = tool_call.get("name", "unknown_tool")
    tool_args = tool_call.get("args", {})
    result_content = ""
    status = "success"

    if result_msg is not None:
        result_content = _truncate_content(getattr(result_msg, "content", "") or "")
        if hasattr(result_msg, "status") and result_msg.status == "error":
            status = "error"

    return TraceRun(
        id=_uid(),
        parent_id=parent_id,
        run_type="tool",
        name=tool_name,
        inputs=tool_args if isinstance(tool_args, dict) else {"raw": str(tool_args)},
        outputs={"content": result_content},
        start_time="",
        end_time="",
        tokens={"input": 0, "output": 0},
        status=status,
        children=[],
    )


def _build_subagent_run(
    tool_call: dict,
    result_msg,
    parent_id: str,
) -> TraceRun:
    """Create a nested chain run for a subagent invocation via the `task` tool."""
    args = tool_call.get("args", {})
    subagent_name = "subagent"
    task_description = ""

    if isinstance(args, dict):
        subagent_name = f"subagent:{args.get('agent', args.get('name', 'specialist'))}"
        task_description = args.get("task", args.get("input", str(args)))
    else:
        task_description = str(args)

    result_content = ""
    status = "success"
    if result_msg is not None:
        result_content = _truncate_content(getattr(result_msg, "content", "") or "")
        if hasattr(result_msg, "status") and result_msg.status == "error":
            status = "error"

    chain_run = TraceRun(
        id=_uid(),
        parent_id=parent_id,
        run_type="chain",
        name=subagent_name,
        inputs={"task": task_description},
        outputs={"content": result_content},
        start_time="",
        end_time="",
        tokens={"input": 0, "output": 0},
        status=status,
        children=[],
    )

    llm_child = TraceRun(
        id=_uid(),
        parent_id=chain_run.id,
        run_type="llm",
        name=f"{subagent_name}:reasoning",
        inputs={"task": task_description},
        outputs={"content": result_content},
        start_time="",
        end_time="",
        tokens={"input": 0, "output": 0},
        status=status,
        children=[],
    )
    chain_run.children.append(llm_child)

    return chain_run


def _match_tool_results(messages: list, start_idx: int, tool_calls: list) -> dict:
    """Match tool_call IDs to their ToolMessage results."""
    result_map: dict = {}
    needed_ids = {tc.get("id") for tc in tool_calls if tc.get("id")}
    if not needed_ids:
        pos = 0
        for j in range(start_idx, len(messages)):
            msg = messages[j]
            if getattr(msg, "type", None) != "tool":
                continue
            if pos < len(tool_calls):
                tc_id = tool_calls[pos].get("id", pos)
                result_map[tc_id] = msg
                pos += 1
            if pos >= len(tool_calls):
                break
        return result_map

    for j in range(start_idx, len(messages)):
        msg = messages[j]
        if getattr(msg, "type", None) != "tool":
            continue
        tc_id = getattr(msg, "tool_call_id", None)
        if tc_id in needed_ids:
            result_map[tc_id] = msg
            needed_ids.discard(tc_id)
        if not needed_ids:
            break

    return result_map


def _distribute_time(root: TraceRun, wall_clock_seconds: float) -> None:
    """Assign ISO-8601 timestamps proportionally based on token counts."""
    now = datetime.now(timezone.utc)

    def _collect_leaf_weights(node: TraceRun) -> list[tuple[TraceRun, int]]:
        if not node.children:
            weight = max(_token_total(node.tokens), 1)
            return [(node, weight)]
        leaves = []
        for child in node.children:
            leaves.extend(_collect_leaf_weights(child))
        return leaves

    leaves = _collect_leaf_weights(root)
    total_weight = sum(w for _, w in leaves)

    cursor = 0.0
    for leaf, weight in leaves:
        fraction = weight / total_weight if total_weight > 0 else 1.0 / len(leaves)
        duration = wall_clock_seconds * fraction

        from datetime import timedelta
        start = now + timedelta(seconds=cursor)
        end = now + timedelta(seconds=cursor + duration)
        leaf.start_time = start.isoformat()
        leaf.end_time = end.isoformat()
        cursor += duration

    def _propagate(node: TraceRun) -> None:
        if not node.children:
            return
        for child in node.children:
            _propagate(child)
        child_starts = [c.start_time for c in node.children if c.start_time]
        child_ends = [c.end_time for c in node.children if c.end_time]
        if child_starts:
            node.start_time = min(child_starts)
        if child_ends:
            node.end_time = max(child_ends)

    _propagate(root)

    if not root.start_time:
        root.start_time = now.isoformat()
    if not root.end_time:
        from datetime import timedelta
        root.end_time = (now + timedelta(seconds=wall_clock_seconds)).isoformat()


def _sum_tokens(node: TraceRun) -> None:
    """Roll up token counts from children into parent nodes."""
    for child in node.children:
        _sum_tokens(child)
    if node.children:
        node.tokens = {
            "input": sum(c.tokens.get("input", 0) for c in node.children),
            "output": sum(c.tokens.get("output", 0) for c in node.children),
        }


def build_trace_tree(messages: list, wall_clock_seconds: float = 0) -> TraceRun:
    """Convert a flat list of LangChain messages into a hierarchical TraceRun tree."""
    root_id = _uid()
    root = TraceRun(
        id=root_id,
        parent_id=None,
        run_type="chain",
        name="chart_review",
        inputs={},
        outputs={},
        start_time="",
        end_time="",
        tokens={"input": 0, "output": 0},
        status="success",
        children=[],
    )

    i = 0
    while i < len(messages):
        msg = messages[i]
        msg_type = getattr(msg, "type", "unknown")

        if msg_type == "human":
            content = getattr(msg, "content", "")
            root.inputs = {"content": content}
            human_run = TraceRun(
                id=_uid(),
                parent_id=root_id,
                run_type="human",
                name="user_question",
                inputs={},
                outputs={"content": content},
                start_time="",
                end_time="",
                tokens={"input": 0, "output": 0},
                status="success",
                children=[],
            )
            root.children.append(human_run)
            i += 1
            continue

        if msg_type == "ai":
            content = getattr(msg, "content", "") or ""
            tool_calls = getattr(msg, "tool_calls", []) or []
            tokens = _extract_tokens(msg)

            if content:
                llm_run = TraceRun(
                    id=_uid(),
                    parent_id=root_id,
                    run_type="llm",
                    name="agent_reasoning",
                    inputs={"context": "agent internal reasoning"},
                    outputs={"content": _truncate_content(content)},
                    start_time="",
                    end_time="",
                    tokens=tokens,
                    status="success",
                    children=[],
                )
                root.children.append(llm_run)

            if tool_calls:
                if not content:
                    call_descriptions = []
                    for tc in tool_calls:
                        tc_name = tc.get("name", "unknown")
                        tc_args = tc.get("args", {})
                        if isinstance(tc_args, dict):
                            args_str = ", ".join(f"{k}={v!r}" for k, v in tc_args.items())
                        else:
                            args_str = str(tc_args)
                        call_descriptions.append(f"{tc_name}({args_str})")
                    decision_text = "Calling: " + ", ".join(call_descriptions)
                    decision_run = TraceRun(
                        id=_uid(),
                        parent_id=root_id,
                        run_type="llm",
                        name="tool_decision",
                        inputs={"context": "agent decides next action"},
                        outputs={"content": decision_text},
                        start_time="",
                        end_time="",
                        tokens=tokens,
                        status="success",
                        children=[],
                    )
                    root.children.append(decision_run)

                result_map = _match_tool_results(messages, i + 1, tool_calls)

                for tc in tool_calls:
                    tc_id = tc.get("id")
                    result_msg = result_map.get(tc_id)
                    tc_name = tc.get("name", "unknown_tool")

                    if tc_name == "task":
                        sub_run = _build_subagent_run(tc, result_msg, root_id)
                        root.children.append(sub_run)
                    else:
                        tool_run = _build_tool_call_run(tc, result_msg, root_id)
                        root.children.append(tool_run)

            if not content and not tool_calls:
                i += 1
                continue

            i += 1
            continue

        if msg_type == "tool":
            i += 1
            continue

        i += 1

    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai":
            ai_content = getattr(msg, "content", "") or ""
            if ai_content:
                root.outputs = {"content": _truncate_content(ai_content)}
            break

    if any(c.status == "error" for c in root.children):
        root.status = "error"

    _sum_tokens(root)
    _distribute_time(root, wall_clock_seconds)

    return root
