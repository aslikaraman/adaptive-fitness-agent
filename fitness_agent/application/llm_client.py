"""The LLMClient interface.

The application layer depends only on this interface. OllamaAdapter
(infrastructure) implements it; FakeLLMClient (tests) implements it
for tests without a model. Each method makes exactly one model call; the retry
loop is in the application services (FUNCTIONAL_FLOW.md §0).
"""

from abc import ABC, abstractmethod

from fitness_agent.domain.models import Exercise, PlanDraft, UserProfile
from fitness_agent.domain.plan import TrainingPlan


class LLMError(Exception):
    """The model returned invalid output or is not available."""


class LLMClient(ABC):
    """What the application needs from a language model."""

    @abstractmethod
    def extract_profile(self, answers: str, previous_error: str | None = None) -> UserProfile:
        """Turn the user's free-text onboarding answers into a UserProfile.

        Raises LLMError on invalid output or when the model is unavailable.
        """

    @abstractmethod
    def generate_plan(
        self,
        profile: UserProfile,
        constraints: str,
        allowed_pool: list[Exercise],
        previous_error: str | None = None,
    ) -> PlanDraft:
        """Draft week 1 of the plan within the Strategy's constraints and the allowed pool.

        Raises LLMError on invalid output or when the model is unavailable.
        """

    @abstractmethod
    def summarize_plan(self, profile: UserProfile, plan: TrainingPlan) -> str:
        """Explain in plain text why the plan fits the profile.

        Raises LLMError when the model is unavailable.
        """

    @abstractmethod
    def explain_changes(self, changes: list[str]) -> str:
        """Explain in two sentences what changed and why (one entry per rule that fired).

        Raises LLMError when the model is unavailable.
        """
