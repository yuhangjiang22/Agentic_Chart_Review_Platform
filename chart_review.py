"""Reviewer execution helpers + single-question CLI for the chart review platform.

Imported by `benchmark.py` for its core helpers, and runnable directly to
score one question on one chart:

    python chart_review.py --chart path/to/patient --question "..." \\
        --domain examples.lung_cancer --levels 1 2 --output results/foo

Public surface:
    LEVEL_MAP        — level_key -> (level_name, factory_module, factory_fn, prompt_attr)
    load_domain(path) — import a domain pack module
    run_reviewer(...) — run one reviewer level and return a ReviewRun
    format_full_trace(messages) — render a flat message list as text
"""

import argparse
import importlib
import json
import os
import sys
import time

from evaluation.metrics import (
    ReviewRun,
    collect_token_usage,
    format_token_usage_report,
    per_message_token_usage,
)
from trace.builder import build_trace_tree


DEFAULT_DOMAIN = "examples.lung_cancer"


def format_full_trace(messages: list) -> str:
    """Format the full message trace including tool calls and results."""
    lines = []
    for msg in messages:
        role = getattr(msg, "type", "unknown")

        if role == "human":
            lines.append("=" * 80)
            lines.append("USER QUESTION")
            lines.append("=" * 80)
            lines.append(msg.content)
            lines.append("")

        elif role == "ai":
            if msg.content:
                lines.append("-" * 80)
                lines.append("AGENT REASONING")
                lines.append("-" * 80)
                lines.append(msg.content)
                lines.append("")

            tool_calls = getattr(msg, "tool_calls", [])
            for tc in tool_calls:
                lines.append(f"  >> TOOL CALL: {tc['name']}({tc.get('args', {})})")

            if tool_calls:
                lines.append("")

        elif role == "tool":
            tool_name = getattr(msg, "name", "unknown_tool")
            content = msg.content or ""
            if len(content) > 2000:
                content = content[:2000] + f"\n  ... [truncated, {len(msg.content)} chars total]"
            lines.append(f"  << TOOL RESULT ({tool_name}):")
            for line in content.split("\n"):
                lines.append(f"     {line}")
            lines.append("")

    return "\n".join(lines)


# Each entry: level_key -> (level_name, factory_module, factory_fn, prompt_attr_name)
LEVEL_MAP = {
    "1": ("naive",  "reviewers.naive_reviewer",  "create_naive_reviewer",  "NAIVE_REVIEWER_PROMPT"),
    "2": ("search", "reviewers.search_reviewer", "create_search_reviewer", "SEARCH_REVIEWER_PROMPT"),
}


def load_domain(module_path: str):
    """Import a domain pack module by its dotted path."""
    return importlib.import_module(module_path)


def run_reviewer(
    level_key: str,
    chart_dir: str,
    question: str,
    model_name: str,
    domain,
    provider: str = "azure",
) -> ReviewRun:
    """Run a single reviewer level and return the ReviewRun.

    `domain` must expose the prompt named in LEVEL_MAP[level_key][3].
    """
    level_name, module_path, factory_name, prompt_attr = LEVEL_MAP[level_key]

    print(f"\n{'=' * 60}")
    print(f"Running {level_name.upper()} reviewer (Level {level_key})...")
    print(f"{'=' * 60}\n")

    module = importlib.import_module(module_path)
    factory = getattr(module, factory_name)
    system_prompt = getattr(domain, prompt_attr)

    agent, metrics = factory(chart_dir, system_prompt=system_prompt, model_name=model_name, provider=provider)

    start_time = time.time()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]}
    )
    wall_clock = time.time() - start_time

    messages = result["messages"]
    final_response = ""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai" and getattr(msg, "content", ""):
            final_response = msg.content
            break
    full_log = format_full_trace(messages)
    input_tokens, output_tokens = collect_token_usage(messages)

    token_report = format_token_usage_report(messages, label=f"{level_name} (Level {level_key})")
    print(token_report)

    trace_tree = build_trace_tree(messages, wall_clock)

    return ReviewRun(
        level=level_name,
        files_read=list(metrics.files_read),
        search_queries=list(metrics.search_queries),
        list_chart_calls=metrics.list_chart_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        wall_clock_seconds=wall_clock,
        final_answer=final_response,
        full_log=full_log,
        trace=trace_tree.to_dict(),
        token_report=token_report,
        per_message_tokens=per_message_token_usage(messages),
    )


def write_run_artifacts(output_dir: str, runs: dict[str, ReviewRun], domain_name: str, question: str) -> None:
    """Write review_<level>.txt, token_usage_<level>.txt, trace_<level>.json, metrics.json."""
    os.makedirs(output_dir, exist_ok=True)
    for level, run in runs.items():
        with open(os.path.join(output_dir, f"review_{level}.txt"), "w") as f:
            f.write(run.full_log)
        if run.token_report:
            with open(os.path.join(output_dir, f"token_usage_{level}.txt"), "w") as f:
                f.write(run.token_report)
        if run.trace is not None:
            with open(os.path.join(output_dir, f"trace_{level}.json"), "w") as f:
                json.dump(run.trace, f, indent=2)

    metrics_data = {
        "domain": domain_name,
        "question": question,
        "runs": {l: r.to_dict() for l, r in runs.items()},
    }
    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(metrics_data, f, indent=2)


def main():
    """Run one question on one chart across the requested reviewer levels."""
    from config import DEFAULT_MODEL, DEFAULT_OLLAMA_MODEL, DEFAULT_PROVIDER

    parser = argparse.ArgumentParser(
        description="Run one chart-review question across reviewer levels."
    )
    parser.add_argument("--chart", required=True, help="Path to a patient chart directory")
    parser.add_argument("--question", required=True, help="Clinical review question")
    parser.add_argument(
        "--levels", nargs="+", default=list(LEVEL_MAP.keys()),
        choices=list(LEVEL_MAP.keys()),
        help=f"Which reviewer levels to run (default: {' '.join(LEVEL_MAP.keys())})",
    )
    parser.add_argument(
        "--domain", default=DEFAULT_DOMAIN,
        help=f"Python module path of the domain pack (default: {DEFAULT_DOMAIN})",
    )
    parser.add_argument(
        "--provider", default=DEFAULT_PROVIDER, choices=["azure", "ollama"],
        help="LLM provider to use (default: from LLM_PROVIDER env var or 'azure')",
    )
    parser.add_argument(
        "--model", default=None,
        help="Model/deployment name (defaults to AZURE_OPENAI_DEPLOYMENT or OLLAMA_MODEL based on provider)",
    )
    parser.add_argument(
        "--output", default="./results",
        help="Output directory for results (default: ./results)",
    )
    args = parser.parse_args()

    if args.model is None:
        args.model = DEFAULT_OLLAMA_MODEL if args.provider == "ollama" else DEFAULT_MODEL

    domain = load_domain(args.domain)
    domain_name = getattr(domain, "NAME", args.domain)

    print(f"Chart Review — domain: {domain_name}")
    print(f"  Chart:    {args.chart}")
    print(f"  Question: {args.question}")
    print(f"  Levels:   {', '.join(args.levels)}")
    print(f"  Provider: {args.provider}")
    print(f"  Model:    {args.model}")
    print(f"  Output:   {args.output}")

    runs: dict[str, ReviewRun] = {}
    for level_key in sorted(args.levels):
        try:
            run = run_reviewer(level_key, args.chart, args.question, args.model, domain, provider=args.provider)
            runs[run.level] = run
            print(f"\n  {run.level} reviewer complete: {run.wall_clock_seconds:.1f}s, "
                  f"{len(run.files_read)} files read, "
                  f"{run.input_tokens} in / {run.output_tokens} out "
                  f"({run.input_tokens + run.output_tokens} total) tokens")
        except Exception as e:
            print(f"\n  ERROR running level {level_key}: {e}", file=sys.stderr)

    if not runs:
        print("No reviewers completed successfully.", file=sys.stderr)
        sys.exit(1)

    write_run_artifacts(args.output, runs, domain_name, args.question)
    print(f"\nResults written to {args.output}/")


if __name__ == "__main__":
    main()
