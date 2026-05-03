"""Level 2: Search Reviewer -- list files, read files, and search keywords."""

from deepagents import create_deep_agent
from config import create_model
from reviewers.tools import create_chart_tools


def create_search_reviewer(
    chart_dir: str,
    system_prompt: str,
    model_name: str | None = None,
    provider: str = "azure",
) -> tuple:
    """Build a search reviewer agent with list_chart, read_note, and search_notes tools.

    `system_prompt` is supplied by the caller (typically the active domain
    pack, e.g. examples.lung_cancer.SEARCH_REVIEWER_PROMPT) so the reviewer
    code itself stays domain-agnostic.

    Returns:
        Tuple of (compiled_agent, metrics).
    """
    tools, metrics = create_chart_tools(chart_dir, enable_search=True)
    model = create_model(model_name, provider=provider)

    agent = create_deep_agent(
        model=model,
        tools=list(tools.values()),
        system_prompt=system_prompt,
    )

    return agent, metrics
