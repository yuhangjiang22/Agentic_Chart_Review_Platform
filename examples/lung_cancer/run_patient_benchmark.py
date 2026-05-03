"""Run the lung-cancer benchmark on a single patient chart.

Thin example wrapper around the platform's `benchmark.run_benchmark`. Edit
`CHART_DIR` / `OUTPUT_DIR` below or pass them as CLI args, then run:

    python -m examples.lung_cancer.run_patient_benchmark
    python -m examples.lung_cancer.run_patient_benchmark --chart path/to/patient
"""

import argparse
import sys
from pathlib import Path

# Make the project root importable when this file is executed directly.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import benchmark  # noqa: E402
from chart_review import load_domain  # noqa: E402
from config import DEFAULT_MODEL  # noqa: E402


CHART_DIR = "patient_profiles/patient_1168000004357584"
OUTPUT_DIR = "results/patient_1168000004357584"


def main():
    parser = argparse.ArgumentParser(description="Lung cancer benchmark — single patient")
    parser.add_argument("--chart", default=CHART_DIR)
    parser.add_argument("--output", default=OUTPUT_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    domain = load_domain("examples.lung_cancer")
    print(f"Running {domain.NAME} benchmark on {args.chart}")
    benchmark.run_benchmark(
        chart_dir=args.chart,
        output_dir=args.output,
        domain=domain,
        model=args.model,
    )


if __name__ == "__main__":
    main()
