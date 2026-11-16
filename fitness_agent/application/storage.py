"""The Storage interface: saves and loads the user's data (implemented by JsonStorage)."""

from abc import ABC, abstractmethod

from fitness_agent.domain.models import Feedback, UserProfile
from fitness_agent.domain.plan import TrainingPlan


class Storage(ABC):
    """Persists the profile, the plan and the feedback."""

    @abstractmethod
    def save_profile(self, profile: UserProfile) -> None:
        """Save the profile, replacing any earlier one."""

    @abstractmethod
    def load_profile(self) -> UserProfile | None:
        """Return the saved profile, or None if there is none."""

    @abstractmethod
    def save_plan(self, plan: TrainingPlan) -> None:
        """Save the plan, replacing any earlier one."""

    @abstractmethod
    def load_plan(self) -> TrainingPlan | None:
        """Return the saved plan, or None if there is none."""

    @abstractmethod
    def save_feedback(self, feedback: Feedback) -> None:
        """Append one feedback to the saved feedback."""

    @abstractmethod
    def load_feedbacks(self) -> list[Feedback]:
        """Return all saved feedback, oldest first."""
