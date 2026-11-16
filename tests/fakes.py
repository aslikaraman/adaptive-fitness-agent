"""Test doubles shared by both halves of the project."""

from fitness_agent.application.llm_client import LLMClient, LLMError
from fitness_agent.domain.models import Exercise, PlanDraft, UserProfile
from fitness_agent.domain.plan import TrainingPlan


class FakeLLMClient(LLMClient):
    """Returns fixed answers, so tests run without Ollama.

    failures = n makes the first n structured calls (extract_profile,
    generate_plan) raise LLMError, to test the retry and the fallback.
    """

    def __init__(
        self,
        profile: UserProfile | None = None,
        plan_draft: PlanDraft | None = None,
        summary: str = "Fake summary.",
        explanation: str = "Fake explanation.",
        failures: int = 0,
    ) -> None:
        """Store the fixed answers; calls lists every method called, in order."""
        self.profile = profile
        self.plan_draft = plan_draft
        self.summary = summary
        self.explanation = explanation
        self.failures = failures
        self.calls: list[str] = []

    def _structured(self, name: str, result):
        """Record the call, fail while failures > 0, else return the fixed result."""
        self.calls.append(name)
        if self.failures > 0:
            self.failures -= 1
            raise LLMError(f"fake failure in {name}")
        if result is None:
            raise LLMError(f"no fixed answer for {name}")
        return result

    def extract_profile(self, answers: str, previous_error: str | None = None) -> UserProfile:
        """Return the fixed profile."""
        return self._structured("extract_profile", self.profile)

    def generate_plan(
        self,
        profile: UserProfile,
        constraints: str,
        allowed_pool: list[Exercise],
        previous_error: str | None = None,
    ) -> PlanDraft:
        """Return the fixed plan draft."""
        return self._structured("generate_plan", self.plan_draft)

    def summarize_plan(self, profile: UserProfile, plan: TrainingPlan) -> str:
        """Return the fixed summary."""
        self.calls.append("summarize_plan")
        return self.summary

    def explain_changes(self, changes: list[str]) -> str:
        """Return the fixed explanation."""
        self.calls.append("explain_changes")
        return self.explanation
