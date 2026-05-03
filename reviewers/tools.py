"""Instrumented chart review tools."""

import os
import re
from dataclasses import dataclass, field
from langchain_core.tools import tool


@dataclass
class ToolMetrics:
    """Tracks all tool invocations during a review run."""
    files_read: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    list_chart_calls: int = 0


def create_chart_tools(
    chart_dir: str, enable_search: bool = False
) -> tuple[dict, ToolMetrics]:
    """Create instrumented chart tools scoped to a chart directory."""
    metrics = ToolMetrics()

    # Patient charts may store notes either directly in chart_dir or under chart_dir/unstructured.
    notes_dir = os.path.join(chart_dir, "unstructured")
    if not os.path.isdir(notes_dir):
        notes_dir = chart_dir

    chart_files = sorted(
        f for f in os.listdir(notes_dir)
        if f.endswith(".txt")
    )

    @tool
    def list_chart() -> str:
        """List all available clinical note filenames in the chart."""
        metrics.list_chart_calls += 1
        return "\n".join(chart_files)

    @tool
    def read_note(filename: str) -> str:
        """Read the full text of a clinical note from the patient chart. Pass the exact filename (e.g. '2023-05-15_PROGRESS_NOTE.txt')."""
        if filename not in chart_files:
            return f"Error: '{filename}' not found in chart. Use list_chart to see available files."
        metrics.files_read.append(filename)
        filepath = os.path.join(notes_dir, filename)
        with open(filepath, "r") as f:
            return f.read()

    tools_dict = {
        "list_chart": list_chart,
        "read_note": read_note,
    }

    if enable_search:
        @tool
        def search_notes(keyword: str) -> str:
            """Search for a keyword across all clinical notes in the patient chart. Returns matching lines with filenames. Case-insensitive."""
            metrics.search_queries.append(keyword)
            results = []
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            for f in chart_files:
                filepath = os.path.join(notes_dir, f)
                with open(filepath, "r") as fh:
                    for line_num, line in enumerate(fh, 1):
                        if pattern.search(line):
                            results.append(f"{f}:{line_num} -- {line.strip()}")
            if not results:
                return f"No matches found for '{keyword}'."
            return "\n".join(results)

        tools_dict["search_notes"] = search_notes

    return tools_dict, metrics
