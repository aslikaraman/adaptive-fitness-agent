"""OllamaAdapter: the LLMClient implementation for a local Ollama model (Adapter pattern).

It translates our LLMClient interface into LangChain calls on ChatOllama
(the adaptee) and translates every LangChain/Ollama failure into LLMError.
Each method makes exactly one model call; the retry loop is in the
application layer.
"""

from fitness_agent.application.llm_client import LLMClient, LLMError
from fitness_agent.domain.models import Exercise, PlanDraft, UserProfile
from fitness_agent.domain.plan import TrainingPlan
from fitness_agent.infrastructure import prompts
from fitness_agent.infrastructure.ollama_model import DEFAULT_MODEL, build_chat_model


class OllamaAdapter(LLMClient):
    """LLMClient backed by a local Ollama model through LangChain."""

    def __init__(self, model: str = DEFAULT_MODEL, num_predict: int = 1000,
                 chat_model=None) -> None:
        """Create the adapter.

        num_predict caps the output length (the model runs on the CPU, so every token costs
        time). chat_model can replace ChatOllama, e.g. with a stub in tests.
        """
        self._chat = chat_model or build_chat_model(model, num_predict=num_predict)

    def _structured(self, schema, messages):
        """One structured call; any failure becomes LLMError."""
        try:
            result = self._chat.with_structured_output(schema).invoke(messages)
        except Exception as error:  # pylint: disable=broad-exception-caught
            # LangChain, Ollama, httpx and Pydantic each raise their own types; the
            # application only needs to know that this attempt failed and why.
            raise LLMError(f"{type(error).__name__}: {error}") from error
        if not isinstance(result, schema):
            raise LLMError(f"expected {schema.__name__}, got {type(result).__name__}")
        return result

    def _text(self, messages) -> str:
        """One plain-text call; any failure or an empty answer becomes LLMError."""
        try:
            text = self._chat.invoke(messages).content
        except Exception as error:  # pylint: disable=broad-exception-caught
            raise LLMError(f"{type(error).__name__}: {error}") from error
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            raise LLMError("empty answer")
        return text

    def extract_profile(self, answers: str, previous_error: str | None = None) -> UserProfile:
        """Turn the user's free-text onboarding answers into a UserProfile."""
        return self._structured(UserProfile, prompts.profile_messages(answers, previous_error))

    def generate_plan(
        self,
        profile: UserProfile,
        constraints: str,
        allowed_pool: list[Exercise],
        previous_error: str | None = None,
    ) -> PlanDraft:
        """Choose the exercises of week 1 within the constraints and the allowed pool."""
        messages = prompts.plan_messages(profile, constraints, allowed_pool, previous_error)
        return self._structured(PlanDraft, messages)

    def summarize_plan(self, profile: UserProfile, plan: TrainingPlan) -> str:
        """Explain in plain text why the plan fits the profile."""
        return self._text(prompts.summary_messages(profile, plan))

    def explain_changes(self, changes: list[str]) -> str:
        """Explain in two sentences what changed and why."""
        return self._text(prompts.explanation_messages(changes))
