"""Metrics collection for chart review runs."""

from dataclasses import dataclass, field


# USD per 1,000,000 tokens. Update or extend as new models / rates are needed.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-5.2": {"input": 1.93, "cached_input": 0.20, "output": 15.40},
}
DEFAULT_PRICING_MODEL = "gpt-5.2"


@dataclass
class ReviewRun:
    """Captured data from a single reviewer run."""
    level: str
    files_read: list[str]
    search_queries: list[str]
    list_chart_calls: int
    input_tokens: int
    output_tokens: int
    wall_clock_seconds: float
    final_answer: str
    full_log: str
    trace: dict | None = None
    token_report: str = ""
    per_message_tokens: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "level": self.level,
            "files_read": self.files_read,
            "files_read_count": len(self.files_read),
            "search_queries": self.search_queries,
            "search_query_count": len(self.search_queries),
            "list_chart_calls": self.list_chart_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "wall_clock_seconds": self.wall_clock_seconds,
            "final_answer": self.final_answer,
            "per_message_tokens": self.per_message_tokens,
        }
        if self.trace is not None:
            d["trace"] = self.trace
        return d


def _message_tokens(msg) -> tuple[int, int, int]:
    """Return (input_tokens, output_tokens, cached_input_tokens) for one message.

    Prefers response_metadata.token_usage (Azure/OpenAI shape), falls back to
    usage_metadata (LangChain-standard shape) so the helpers stay correct if the
    underlying provider changes. cached_input_tokens is the portion of input
    served from the prompt cache (billed at the cached-input rate).
    """
    usage = getattr(msg, "response_metadata", {}).get("token_usage") or {}
    if usage:
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        return prompt, completion, cached
    um = getattr(msg, "usage_metadata", None) or {}
    cached = (um.get("input_token_details") or {}).get("cache_read", 0)
    return um.get("input_tokens", 0), um.get("output_tokens", 0), cached


def collect_token_usage(messages: list) -> tuple[int, int]:
    """Total (input_tokens, output_tokens) across messages. Back-compat shape."""
    input_tokens = 0
    output_tokens = 0
    for msg in messages:
        i, o, _ = _message_tokens(msg)
        input_tokens += i
        output_tokens += o
    return input_tokens, output_tokens


def collect_token_usage_detailed(messages: list) -> tuple[int, int, int]:
    """Total (input, output, cached_input) tokens across messages."""
    i_sum = o_sum = c_sum = 0
    for msg in messages:
        i, o, c = _message_tokens(msg)
        i_sum += i
        o_sum += o
        c_sum += c
    return i_sum, o_sum, c_sum


def per_message_token_usage(messages: list) -> list[dict]:
    """Per-step token breakdown for messages that carry usage metadata.

    Only messages with non-zero usage are returned, since tool/human messages
    do not produce token charges. Each entry: step (1-indexed among billed
    steps), msg_index (index in the original messages list), input_tokens,
    cached_input_tokens, output_tokens, total_tokens, tool_calls (count).
    """
    rows: list[dict] = []
    step = 0
    for idx, msg in enumerate(messages):
        i, o, c = _message_tokens(msg)
        if i == 0 and o == 0:
            continue
        step += 1
        rows.append({
            "step": step,
            "msg_index": idx,
            "input_tokens": i,
            "cached_input_tokens": c,
            "output_tokens": o,
            "total_tokens": i + o,
            "tool_calls": len(getattr(msg, "tool_calls", []) or []),
        })
    return rows


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    model: str = DEFAULT_PRICING_MODEL,
) -> dict | None:
    """Cost in USD given token counts and a pricing model. Returns None if model unknown.

    Cached-input tokens are billed at the cached rate; the remainder of input is
    billed at the standard input rate.
    """
    rates = MODEL_PRICING.get(model)
    if rates is None:
        return None
    non_cached = max(input_tokens - cached_input_tokens, 0)
    in_cost = non_cached * rates["input"] / 1_000_000
    cache_cost = cached_input_tokens * rates["cached_input"] / 1_000_000
    out_cost = output_tokens * rates["output"] / 1_000_000
    return {
        "model": model,
        "non_cached_input_tokens": non_cached,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": round(in_cost, 6),
        "cached_input_cost_usd": round(cache_cost, 6),
        "output_cost_usd": round(out_cost, 6),
        "total_cost_usd": round(in_cost + cache_cost + out_cost, 6),
    }


def format_token_usage_report(
    messages: list,
    label: str = "",
    pricing_model: str = DEFAULT_PRICING_MODEL,
) -> str:
    """Per-step + cumulative token usage with a cost estimate at the bottom."""
    rows = per_message_token_usage(messages)
    total_in, total_out, total_cached = collect_token_usage_detailed(messages)

    lines = []
    header = "TOKEN USAGE" + (f" — {label}" if label else "")
    lines.append("=" * 88)
    lines.append(header)
    lines.append("=" * 88)
    lines.append(
        f"{'Step':<5} {'Input':>10} {'Cached':>10} {'Output':>10} "
        f"{'Total':>10} {'CumIn':>10} {'CumOut':>10} {'Tools':>8}"
    )
    lines.append("-" * 88)

    cum_in = cum_out = 0
    for r in rows:
        cum_in += r["input_tokens"]
        cum_out += r["output_tokens"]
        lines.append(
            f"{r['step']:<5} {r['input_tokens']:>10} {r['cached_input_tokens']:>10} "
            f"{r['output_tokens']:>10} {r['total_tokens']:>10} "
            f"{cum_in:>10} {cum_out:>10} {r['tool_calls']:>8}"
        )

    lines.append("-" * 88)
    lines.append(
        f"{'TOTAL':<5} {total_in:>10} {total_cached:>10} {total_out:>10} "
        f"{total_in + total_out:>10}"
    )

    cost = estimate_cost(total_in, total_out, total_cached, model=pricing_model)
    if cost is not None:
        rates = MODEL_PRICING[pricing_model]
        lines.append("-" * 88)
        lines.append(f"COST ESTIMATE ({pricing_model}, USD per 1M tokens: "
                     f"input ${rates['input']:.2f}, cached ${rates['cached_input']:.2f}, "
                     f"output ${rates['output']:.2f})")
        lines.append(
            f"  Non-cached input: {cost['non_cached_input_tokens']:>10} tok  "
            f"= ${cost['input_cost_usd']:.4f}"
        )
        lines.append(
            f"  Cached input:     {cost['cached_input_tokens']:>10} tok  "
            f"= ${cost['cached_input_cost_usd']:.4f}"
        )
        lines.append(
            f"  Output:           {cost['output_tokens']:>10} tok  "
            f"= ${cost['output_cost_usd']:.4f}"
        )
        lines.append(f"  TOTAL: ${cost['total_cost_usd']:.4f}")
    lines.append("=" * 88)
    return "\n".join(lines)
