"""Level 1: Naive Reviewer -- can only list files and read them."""

from deepagents import create_deep_agent
from config import create_model
from reviewers.tools import create_chart_tools


def create_naive_reviewer(
    chart_dir: str,
    system_prompt: str,
    model_name: str | None = None,
    provider: str = "azure",
) -> tuple:
    """Build a naive reviewer agent with only list_chart and read_note tools.

    `system_prompt` is supplied by the caller (typically the active domain
    pack, e.g. examples.lung_cancer.NAIVE_REVIEWER_PROMPT) so the reviewer
    code itself stays domain-agnostic.

    Returns:
        Tuple of (compiled_agent, metrics).
    """
    tools, metrics = create_chart_tools(chart_dir, enable_search=False)
    model = create_model(model_name, provider=provider)

    agent = create_deep_agent(
        model=model,
        tools=list(tools.values()),
        system_prompt=system_prompt,
    )

    return agent, metrics
