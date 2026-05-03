"""Lung cancer molecular testing — domain pack for the chart review platform.

The platform loads a domain by importing a module and reading these attributes:

  NAME, QUESTIONS, TIER_NAMES, NAIVE_REVIEWER_PROMPT, SEARCH_REVIEWER_PROMPT.

Any module that exposes these names can be passed via `--domain <module>`.
"""

from examples.lung_cancer.questions import (
    NAME,
    QUESTIONS,
    TIER_NAMES,
)
from examples.lung_cancer.reviewer_prompts import (
    NAIVE_REVIEWER_PROMPT,
    SEARCH_REVIEWER_PROMPT,
)
