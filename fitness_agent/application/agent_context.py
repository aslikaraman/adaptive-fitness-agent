"""AgentContext: what the coach agent's tools may read and do (application layer).

The agent lives in the infrastructure layer; through this context it reads the profile and
the plan, submits a Feedback and undoes the last change, without knowing the storage or the
services behind it.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fitness_agent.application.storage import Storage
from fitness_agent.domain.models import Feedback, UserProfile
from fitness_agent.domain.plan import TrainingPlan


def record_only(feedback: Feedback) -> list[str]:
    """Accept the Feedback without adapting: the feedback state adapts the plan right after."""
    del feedback
    return []


@dataclass
class AgentContext:
    """The agent's view of the application."""

    storage: Storage
    submit: Callable[[Feedback], list[str]] | None = record_only
    undo: Callable[[], str] | None = None

    def profile(self) -> UserProfile | None:
        """The saved profile."""
        return self.storage.load_profile()

    def plan(self) -> TrainingPlan | None:
        """The saved plan."""
        return self.storage.load_plan()
