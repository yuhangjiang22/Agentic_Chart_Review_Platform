"""Domain-agnostic benchmark runner for the chart review platform.

Walks every question in a domain pack across the configured reviewer levels
and emits per-question artifacts plus a Markdown comparison report.

The domain pack must expose:
    NAME, QUESTIONS, NAIVE_REVIEWER_PROMPT, SEARCH_REVIEWER_PROMPT.
    TIER_NAMES is optional (used only for human-readable tier labels).

Each question runs independently (no cross-question memory).

Usage:
    python benchmark.py --chart path/to/patient --output results/foo
    python benchmark.py --chart path/to/patient --domain examples.lung_cancer
"""

import argparse
import json
import os
import time

from chart_review import run_reviewer, load_domain, LEVEL_MAP


DEFAULT_DOMAIN = "examples.lung_cancer"
LEVELS = list(LEVEL_MAP.keys())                                  # e.g. ["1", "2"]
LEVEL_NAMES = {k: v[0] for k, v in LEVEL_MAP.items()}            # {"1": "naive", "2": "search"}


def run_benchmark(
    chart_dir: str,
    output_dir: str,
    domain,
    model: str,
) -> None:
    questions = domain.QUESTIONS
    domain_name = getattr(domain, "NAME", "Chart Review")

    model_slug = model.split("/")[-1]
    out_root = os.path.join(output_dir, model_slug)
    os.makedirs(out_root, exist_ok=True)

    results = {}        # (q_id, level) -> ReviewRun
    total = len(questions) * len(LEVELS)
    done = 0
    t0 = time.time()

    print(f"{domain_name} Benchmark: {len(questions)} questions x {len(LEVELS)} levels = {total} runs")
    print(f"Model: {model}\n")

    for q_id, question, expected, tier, category in questions:
        print(f"\n{'#' * 70}")
        print(f"# [{category}] Tier {tier} | {q_id}: {question[:60]}...")
        print(f"{'#' * 70}")

        qd = os.path.join(out_root, q_id)
        os.makedirs(qd, exist_ok=True)

        for level in LEVELS:
            done += 1
            lname = LEVEL_NAMES[level]
            print(f"\n  [{done}/{total}] L{level}-{lname}")
            try:
                run = run_reviewer(level, chart_dir, question, model, domain)
                results[(q_id, level)] = run
                with open(os.path.join(qd, f"review_{lname}.txt"), "w") as f:
                    f.write(run.full_log)
                if run.token_report:
                    with open(os.path.join(qd, f"token_usage_{lname}.txt"), "w") as f:
                        f.write(run.token_report)
                if run.trace is not None:
                    with open(os.path.join(qd, f"trace_{lname}.json"), "w") as f:
                        json.dump(run.trace, f, indent=2)
                tok = run.input_tokens + run.output_tokens
                print(f"    OK  {run.wall_clock_seconds:6.1f}s | "
                      f"{tok:>7,} tok | "
                      f"{len(run.files_read):>2} files | "
                      f"{len(run.search_queries)} searches")
            except Exception as e:
                results[(q_id, level)] = None
                print(f"    ERR {e}")

    elapsed = time.time() - t0
    print(f"\n\nDone: {done} runs in {elapsed:.0f}s")
    write_markdown_report(results, model, elapsed, out_root, domain)


def fmt(v, kind="int"):
    if v is None:
        return "ERR"
    if kind == "float":
        return f"{v:.1f}"
    if kind == "comma":
        return f"{v:,}"
    return str(v)


def write_markdown_report(results, model, elapsed, output_dir, domain) -> None:
    """Emit comparison.md, all_metrics.json, question_metadata.json."""
    questions = domain.QUESTIONS
    tier_names = getattr(domain, "TIER_NAMES", {})
    domain_name = getattr(domain, "NAME", "Chart Review")

    actual_count = sum(1 for (_q, _l), r in results.items() if r)
    level_headers = [f"L{level} {LEVEL_NAMES.get(level, level).title()}" for level in LEVELS]

    lines = []
    lines.append(f"# {domain_name} Benchmark: {len(LEVELS)} Agent Levels x {len(questions)} Questions")
    lines.append(f"**Model:** `{model}`")
    lines.append(f"**Total time:** {elapsed:.0f}s")
    lines.append(f"**Runs:** {actual_count} executed\n")

    lines.append("## Questions by Tier\n")
    current_tier = -1
    for i, (q_id, q, expected, tier, category) in enumerate(questions, 1):
        if tier != current_tier:
            current_tier = tier
            label = tier_names.get(tier)
            heading = f"Tier {tier}: {label}" if label else f"Tier {tier}"
            lines.append(f"\n### {heading}\n")
        lines.append(f"{i}. **{q_id}** [{category}]: {q}")
    lines.append("")

    lines.append("## Results Summary\n")
    header = (
        f"| {'Question':<12} | {'Tier':>4} | {'Metric':<10} | "
        + " | ".join(f"{name:>10}" for name in level_headers)
        + " |"
    )
    sep = f"|{'-'*14}|{'-'*6}|{'-'*12}|" + "|".join("-" * 12 for _ in LEVELS) + "|"
    lines.append(header)
    lines.append(sep)

    for q_id, _, _, tier, _ in questions:
        for metric_name, fn, fkind in [
            ("Time (s)", lambda r: r.wall_clock_seconds, "float"),
            ("Tokens", lambda r: r.input_tokens + r.output_tokens, "comma"),
            ("Files", lambda r: len(r.files_read), "int"),
            ("Searches", lambda r: len(r.search_queries), "int"),
        ]:
            vals = []
            for level in LEVELS:
                r = results.get((q_id, level))
                v = fn(r) if r else None
                vals.append(fmt(v, fkind))
            label = q_id if metric_name == "Time (s)" else ""
            tier_str = str(tier) if metric_name == "Time (s)" else ""
            lines.append(
                f"| {label:<12} | {tier_str:>4} | {metric_name:<10} | "
                + " | ".join(f"{v:>10}" for v in vals)
                + " |"
            )
        lines.append(sep)
    lines.append("")

    lines.append("## Level Averages\n")
    lines.append(
        f"| {'Metric':<15} | "
        + " | ".join(f"{name:>10}" for name in level_headers)
        + " |"
    )
    lines.append(f"|{'-'*17}|" + "|".join("-" * 12 for _ in LEVELS) + "|")
    for metric_name, fn, fkind in [
        ("Avg Time (s)", lambda r: r.wall_clock_seconds, "float"),
        ("Avg Tokens", lambda r: r.input_tokens + r.output_tokens, "comma"),
        ("Avg Files", lambda r: len(r.files_read), "float"),
        ("Avg Searches", lambda r: len(r.search_queries), "float"),
    ]:
        vals = []
        for level in LEVELS:
            level_vals = []
            for q_id, _, _, _, _ in questions:
                r = results.get((q_id, level))
                if r:
                    level_vals.append(fn(r))
            if level_vals:
                vals.append(fmt(sum(level_vals) / len(level_vals), fkind))
            else:
                vals.append("ERR")
        lines.append(f"| {metric_name:<15} | " + " | ".join(f"{v:>10}" for v in vals) + " |")
    lines.append("")

    lines.append("## Per-Tier Averages\n")
    lines.append(
        f"| {'Tier':<20} | "
        + " | ".join(f"{name:>10}" for name in level_headers)
        + " |"
    )
    lines.append(f"|{'-'*22}|" + "|".join("-" * 12 for _ in LEVELS) + "|")
    tier_nums = sorted({t for _, _, _, t, _ in questions})
    for tier_num in tier_nums:
        tier_qs = [(q_id, q, e, t, c) for q_id, q, e, t, c in questions if t == tier_num]
        tier_label = tier_names.get(tier_num, "")
        vals = []
        for level in LEVELS:
            level_times = []
            for q_id, _, _, _, _ in tier_qs:
                r = results.get((q_id, level))
                if r:
                    level_times.append(r.wall_clock_seconds)
            if level_times:
                vals.append(fmt(sum(level_times) / len(level_times), "float"))
            else:
                vals.append("ERR")
        lines.append(f"| T{tier_num} {tier_label:<17} | " + " | ".join(f"{v:>10}" for v in vals) + " |")
    lines.append("")

    lines.append("## Answer Excerpts (first 500 chars)\n")
    for q_id, question, _, tier, category in questions:
        lines.append(f"### {q_id} [T{tier} {category}]: {question}\n")
        for level in LEVELS:
            lname = LEVEL_NAMES[level]
            r = results.get((q_id, level))
            lines.append(f"**L{level} ({lname}):**")
            if r:
                ans = r.final_answer.strip()
                if len(ans) > 500:
                    ans = ans[:500] + "..."
                lines.append(ans)
            else:
                lines.append("ERROR")
            lines.append("")
        lines.append("---\n")

    report = "\n".join(lines)

    with open(os.path.join(output_dir, "comparison.md"), "w") as f:
        f.write(report)

    metrics = {}
    for (q_id, level), r in results.items():
        if r:
            lname = LEVEL_NAMES[level]
            metrics[f"{q_id}__{lname}"] = r.to_dict()
    with open(os.path.join(output_dir, "all_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    q_meta = {}
    for q_id, question, expected, tier, category in questions:
        q_meta[q_id] = {
            "order": next(i for i, (qid, *_rest) in enumerate(questions, 1) if qid == q_id),
            "question": question,
            "expected_answer": expected,
            "tier": tier,
            "tier_name": tier_names.get(tier, ""),
            "category": category,
        }
    with open(os.path.join(output_dir, "question_metadata.json"), "w") as f:
        json.dump(q_meta, f, indent=2)

    print(f"\nSaved to {output_dir}/comparison.md")


def main():
    from config import DEFAULT_MODEL

    parser = argparse.ArgumentParser(
        description="Run all questions in a domain pack across reviewer levels."
    )
    parser.add_argument("--chart", required=True, help="Path to a patient chart directory")
    parser.add_argument("--output", default="./benchmark_results", help="Output base directory")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN,
                        help=f"Python module path of the domain pack (default: {DEFAULT_DOMAIN})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Azure OpenAI deployment name (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    domain = load_domain(args.domain)
    run_benchmark(
        chart_dir=args.chart,
        output_dir=args.output,
        domain=domain,
        model=args.model,
    )


if __name__ == "__main__":
    main()
