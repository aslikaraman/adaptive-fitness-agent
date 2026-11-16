"""OnboardingService: turns the onboarding answers into a saved UserProfile (FUNCTIONAL_FLOW §3)."""

from fitness_agent.application.llm_client import LLMClient, LLMError
from fitness_agent.application.retry import with_retries
from fitness_agent.application.storage import Storage
from fitness_agent.domain.models import UserProfile


class OnboardingService:
    """Profile extraction with the retry rule, and saving the profile."""

    def __init__(self, llm: LLMClient, storage: Storage) -> None:
        """The LLM reads the answers; the storage keeps the profile."""
        self._llm = llm
        self._storage = storage

    def extract(self, answers: str) -> UserProfile | None:
        """Return the profile read from the free-text answers, or None after 3 failed attempts."""
        return with_retries(lambda error: self._llm.extract_profile(answers, error), (LLMError,))

    def save(self, profile: UserProfile) -> None:
        """Save the profile."""
        self._storage.save_profile(profile)
