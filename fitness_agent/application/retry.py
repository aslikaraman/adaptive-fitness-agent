"""The retry loop for structured LLM steps (Retry with Fallback, FUNCTIONAL_FLOW.md §0).

Every structured step gets at most MAX_ATTEMPTS attempts. Each retry receives the error of the
previous attempt, so the prompt can say what was wrong. If every attempt fails, the caller
uses its deterministic fallback.
"""

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

MAX_ATTEMPTS = 3


def with_retries(attempt: Callable[[str | None], T], errors: tuple[type[Exception], ...],
                 attempts: int = MAX_ATTEMPTS) -> T | None:
    """Call attempt(previous_error) until it succeeds; return None after the last failure.

    Only the given error types count as a failed attempt; any other error is a bug and is raised.
    """
    previous_error = None
    for _ in range(attempts):
        try:
            return attempt(previous_error)
        except errors as error:
            previous_error = str(error)
    return None
