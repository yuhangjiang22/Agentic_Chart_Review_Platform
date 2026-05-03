# Agentic Chart Review Platform

A domain-agnostic pipeline that answers structured clinical questions about a
patient's chart by reading clinical notes. The reviewers are built on top of [`deepagents.create_deep_agent`](https://pypi.org/project/deepagents/)
and use Azure OpenAI for the underlying LLM.

---

## Project Layout

```
Agentic_Chart_Review_Platform/
├── benchmark.py                 # CLI: run all questions in a domain pack
├── chart_review.py              # CLI: run one question + reviewer execution helpers
├── config.py                    # Azure OpenAI client (reads .env)
│
├── reviewers/
│   ├── naive_reviewer.py        # Level 1: list_chart + read_note
│   ├── search_reviewer.py       # Level 2: list_chart + read_note + search_notes
│   ├── prompt_skeleton.py       # Domain-agnostic system-prompt builder
│   └── tools.py                 # Instrumented chart tools + ToolMetrics
│
├── evaluation/
│   └── metrics.py               # ReviewRun dataclass + token/cost helpers
│
├── trace/
│   ├── schema.py                # TraceRun (recursive node) dataclass
│   └── builder.py               # Flat LangChain messages -> hierarchical TraceRun
│
└── examples/
    └── lung_cancer/             # Reference domain pack
        ├── __init__.py          # Re-exports the public domain attributes
        ├── questions.py         # 18 lung-cancer molecular-testing questions
        ├── reviewer_prompts.py  # System prompts (lung cancer)
        └── run_patient_benchmark.py  # Convenience wrapper for one patient
```

The platform code (top-level `*.py`, `reviewers/`, `evaluation/`, `trace/`) is
written without any domain knowledge — it loads a domain pack at runtime via
`--domain <python.module.path>`.

---

## Reviewer Levels

The two reviewer architectures live in [reviewers/](reviewers/) and share the
chart tools defined in [reviewers/tools.py](reviewers/tools.py).

| Level | Name   | Tools available                              | Use case                                       |
|-------|--------|----------------------------------------------|------------------------------------------------|
| 1     | naive  | `list_chart`, `read_note`                    | Baseline; must read entire notes one at a time |
| 2     | search | `list_chart`, `read_note`, `search_notes`    | Can grep for keywords before reading           |

Each tool call is recorded by `ToolMetrics` so the run summary captures which
files were read, how many `list_chart` calls happened, and which keywords were
searched.

---

## Domain Packs

A **domain pack** is any Python module that exposes the following attributes:

| Attribute                | Type                                                  | Purpose                                                                 |
|--------------------------|-------------------------------------------------------|-------------------------------------------------------------------------|
| `NAME`                   | `str`                                                 | Human-readable label used in headers and reports                        |
| `QUESTIONS`              | `list[(id, text, expected, tier, category)]`          | All questions to ask, organized by tier                                 |
| `TIER_NAMES`             | `dict[int, str]` *(optional)*                         | Display name for each tier                                              |
| `NAIVE_REVIEWER_PROMPT`  | `str`                                                 | System prompt for Level 1 (build with `reviewers.prompt_skeleton.build_naive_prompt`) |
| `SEARCH_REVIEWER_PROMPT` | `str`                                                 | System prompt for Level 2 (build with `reviewers.prompt_skeleton.build_search_prompt`) |

The bundled lung-cancer pack at [examples/lung_cancer/](examples/lung_cancer/)
implements every attribute. To add a new use case, create a sibling
`examples/<your_domain>/` package that exposes the same names.

---

## Setup

### Dependencies

```bash
pip install -r requirements.txt
```

See [requirements.txt](requirements.txt) for the pinned-by-name list
(`langchain-openai`, `langchain-core`, `python-dotenv`, `deepagents`).

### `.env` file

[config.py](config.py) loads `.env` from the repo root via `python-dotenv`. A
template is provided at [.env.example](.env.example) — copy it and fill in
your values:

```bash
cp .env.example .env
# then edit .env with your real Azure OpenAI credentials
```

Required keys:

```
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-5.2          # default deployment for the reviewers
AZURE_OPENAI_API_VERSION=2024-06-01      # optional; defaults to 2024-06-01
```

Without `.env` any run fails fast at [config.py](config.py) with a clear error
message.

### Chart directory

A "chart" is a directory of `.txt` clinical notes. The tools auto-detect either
shape:

```
patient_<id>/                 # (a) flat layout
    2023-05-15_PROGRESS.txt
    2023-06-02_PATHOLOGY.txt

patient_<id>/                 # (b) under unstructured/
    note_metadata.csv
    unstructured/
        2023-05-15_PROGRESS.txt
        ...
```

See [reviewers/tools.py](reviewers/tools.py) for the resolution rule.

---

## Running

There are two entry points: `chart_review.py` for a single question on one
chart, and `benchmark.py` for every question in a domain pack on one chart.

### A) One question, one chart

```bash
python chart_review.py \
  --chart lung-cancer-patient-profile/patient_xxx \
  --question "Was genomic testing performed?" \
  --domain examples.lung_cancer \
  --levels 1 2 \
  --output results/example_run
```

Flags:
- `--chart` — path to the patient directory (required)
- `--question` — the question to answer (required)
- `--levels` — subset of `1 2` (default: both)
- `--domain` — Python module path of the domain pack (default: `examples.lung_cancer`)
- `--model` — Azure deployment name (default: from `AZURE_OPENAI_DEPLOYMENT`)
- `--output` — output directory (default: `./results`)

Writes `review_<level>.txt`, `token_usage_<level>.txt`, `trace_<level>.json`,
and `metrics.json` to the output directory.

### B) Full benchmark on one chart

```bash
python benchmark.py \
  --chart lung-cancer-patient-profile/patient_xxx \
  --domain examples.lung_cancer \
  --output benchmark_results/patient_xxx
```

Flags:
- `--chart` — path to the patient directory (required)
- `--output` — output base directory (default: `./benchmark_results`)
- `--domain` — Python module path of the domain pack (default: `examples.lung_cancer`)
- `--model` — Azure deployment name (default: from `AZURE_OPENAI_DEPLOYMENT`)

### Convenience wrapper for the lung cancer example

```bash
python -m examples.lung_cancer.run_patient_benchmark --chart path/to/patient
```

The lung-cancer pack walks all 18 molecular-testing questions
(MT0a → MT12, defined in
[examples/lung_cancer/questions.py](examples/lung_cancer/questions.py)).

### All patients

Loop in shell:

```bash
for p in lung-cancer-patient-profile/patient_*; do
  python benchmark.py \
    --chart "$p" \
    --domain examples.lung_cancer \
    --output "benchmark_results/$(basename "$p")"
done
```

---

## Output Artifacts

### Single-question runs (`chart_review.py`)

```
output_dir/
├── review_<level>.txt          # Full message trace (human/AI/tool turns)
├── token_usage_<level>.txt     # Per-step token monitor (see below)
├── trace_<level>.json          # Hierarchical TraceRun tree
└── metrics.json                # Aggregated metrics for all levels
```

### Benchmark runs (`benchmark.py`)

```
output_dir/<model>/
├── <q_id>/
│   ├── review_<level>.txt       # Full message trace (human/AI/tool turns)
│   ├── token_usage_<level>.txt  # Per-step token monitor (see below)
│   └── trace_<level>.json       # Hierarchical TraceRun tree
├── comparison.md                # Aggregate Markdown report across all questions
├── all_metrics.json             # All ReviewRuns keyed by "<q_id>__<level>"
└── question_metadata.json       # Question registry (id, text, tier, category)
```

---

## Token Usage Monitoring

Every reviewer run produces a per-step token table that is **printed to stdout
during the run** and **saved to `token_usage_<level>.txt`**.

Example:

```
========================================================================================
TOKEN USAGE — naive (Level 1)
========================================================================================
Step       Input     Cached     Output      Total      CumIn     CumOut    Tools
----------------------------------------------------------------------------------------
1           1200          0         80       1280       1200         80        1
2           1450        512         60       1510       2650        140        2
3           2100       1024        220       2320       4750        360        0
----------------------------------------------------------------------------------------
TOTAL       4750       1536        360       5110
========================================================================================
```

Columns:

- **Step** — 1-indexed AI turn (only billed messages are listed; tool/human
  turns are skipped because they do not produce token charges)
- **Input** — total input/prompt tokens for the step
- **Cached** — portion of input served from the prompt cache
- **Output** — completion tokens
- **Total** — `Input + Output`
- **CumIn / CumOut** — running totals across the run
- **Tools** — number of tool calls emitted on that step

A summary line in the run-complete output also breaks input vs. output:

```
naive reviewer complete: 12.4s, 7 files read, 4750 in / 360 out (5110 total) tokens
```

---

## Trace Module

[trace/](trace/) is a homegrown, OpenTelemetry-lite representation of one
reviewer run.

`build_trace_tree(messages, wall_clock_seconds)` in
[trace/builder.py](trace/builder.py) walks the flat list of LangChain messages
and produces a hierarchical `TraceRun` tree:

- A root `chain` node named `chart_review`
- `human` child for the user question
- `llm` children for each AI turn (`agent_reasoning` if the AI emitted text,
  `tool_decision` if it only emitted tool calls)
- `tool` children for each tool call, paired with their results via
  `tool_call_id`
- Token counts aggregated bottom-up; wall-clock time apportioned across nodes

The serialized JSON (`trace_<level>.json`) provides an expandable per-step
view of the run.

---

## Adding a New Domain

The shortest path to a new use case is to copy and adapt the lung-cancer pack:

```bash
cp -r examples/lung_cancer examples/my_domain
```

Then in `examples/my_domain/`:

1. **questions.py** — replace `QUESTIONS` and `TIER_NAMES` with content for
   your use case.
2. **reviewer_prompts.py** — replace `ROLE`, `CLINICAL_CONTEXT`, and
   `SEARCH_TIPS` with domain-specific blurbs. The
   [`reviewers.prompt_skeleton`](reviewers/prompt_skeleton.py) helpers
   (`build_naive_prompt`, `build_search_prompt`) supply the uniform tool
   descriptions, mandatory rules, and JSON output schema — you only write
   the role descriptor and the clinical content.
3. **`__init__.py`** — adjust the imports if you renamed any modules.

Then run with `--domain examples.my_domain` everywhere.
