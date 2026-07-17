"""Token counting helpers for Token Atlas tooling."""

from __future__ import annotations

import math
from typing import Literal


TokenEstimator = Literal["exact", "approximate"]


def count_tokens(text: str, model: str | None = None) -> tuple[int, TokenEstimator]:
    if not model:
        return approximate_tokens(text), "approximate"

    try:
        import tiktoken  # type: ignore
    except ImportError:
        return approximate_tokens(text), "approximate"

    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return approximate_tokens(text), "approximate"
    return len(encoding.encode(text)), "exact"


def approximate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)
