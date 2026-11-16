"""Tests for OllamaAdapter.

The unit tests replace ChatOllama with a stub, so they run without Ollama.
The tests marked "ollama" call the real local model (run with: pytest -m ollama).
"""

import httpx
import pytest
from langchain_core.messages import AIMessage

from fitness_agent.application.llm_client import LLMError
from fitness_agent.domain.models import Exercise, PlanDraft, UserProfile
from fitness_agent.domain.plan import TrainingPlan
from fitness_agent.infrastructure.ollama_adapter import OllamaAdapter

PROFILE = UserProfile(age=25, fitness_level="beginner", goal="strength", days_per_week=3)
POOL = [Exercise(id="goblet_squat", name="Goblet squat", movement_pattern="squat",
                 required_equipment=["dumbbells"], is_compound=True, default_rep_range=(8, 12),
                 load_type="kg", level="beginner"),
        Exercise(id="push_up", name="Push-up", movement_pattern="push",
                 required_equipment=["bodyweight"], is_compound=True, default_rep_range=(8, 20),
                 load_type="bw", level="beginner")]


class StubChat:
    """Stands in for ChatOllama: returns a fixed result or raises a fixed error."""

    def __init__(self, result=None, error=None):
        """result is returned by invoke(); error is raised instead, if given."""
        self.result = result
        self.error = error
        self.messages = None

    def with_structured_output(self, _schema):
        """The stub returns the same object for structured calls."""
        return self

    def invoke(self, messages):
        """Record the messages, then raise or return."""
        self.messages = messages
        if self.error:
            raise self.error
        return self.result


def test_extract_profile_returns_the_parsed_profile():
    """A valid structured answer is returned as it is."""
    adapter = OllamaAdapter(chat_model=StubChat(result=PROFILE))
    assert adapter.extract_profile("25, beginner, strength, 3 days") == PROFILE


def test_previous_error_is_sent_on_a_retry():
    """The retry prompt tells the model what was wrong."""
    chat = StubChat(result=PROFILE)
    OllamaAdapter(chat_model=chat).extract_profile("answers", previous_error="age must be 14-90")
    assert "age must be 14-90" in chat.messages[-1][1]


def test_unreachable_model_raises_llm_error():
    """A connection error becomes LLMError."""
    adapter = OllamaAdapter(chat_model=StubChat(error=httpx.ConnectError("refused")))
    with pytest.raises(LLMError, match="ConnectError"):
        adapter.generate_plan(PROFILE, "3 sessions", POOL)


def test_wrong_result_type_raises_llm_error():
    """A result that is not the requested schema becomes LLMError."""
    adapter = OllamaAdapter(chat_model=StubChat(result={"sessions": []}))
    with pytest.raises(LLMError):
        adapter.generate_plan(PROFILE, "3 sessions", POOL)


def test_plan_prompt_lists_only_the_allowed_pool():
    """The model only sees the allowed exercises."""
    chat = StubChat(result=PlanDraft(sessions=[]))
    OllamaAdapter(chat_model=chat).generate_plan(PROFILE, "3 sessions", POOL)
    prompt = chat.messages[-1][1]
    assert "goblet_squat" in prompt and "push_up" in prompt


def test_text_methods_return_the_text():
    """summarize_plan() and explain_changes() return the model's text."""
    adapter = OllamaAdapter(chat_model=StubChat(result=AIMessage(content=" Two sentences. ")))
    assert adapter.explain_changes(["squat +1 load step"]) == "Two sentences."
    assert adapter.summarize_plan(PROFILE, TrainingPlan()) == "Two sentences."


def test_empty_text_raises_llm_error():
    """An empty answer counts as a failure (the caller uses the template text)."""
    adapter = OllamaAdapter(chat_model=StubChat(result=AIMessage(content="  ")))
    with pytest.raises(LLMError):
        adapter.explain_changes(["squat +1 load step"])


@pytest.mark.ollama
def test_real_model_extracts_a_profile():
    """Integration: qwen3 turns free text into a valid UserProfile."""
    profile = OllamaAdapter().extract_profile(
        "I'm 30, a beginner, I want to get stronger, I can train 3 days a week, "
        "I have dumbbells, and my knee hurts sometimes.")
    assert profile.age == 30
    assert profile.goal == "strength"
    assert "dumbbells" in profile.equipment


@pytest.mark.ollama
def test_real_model_chooses_exercises_from_the_pool():
    """Integration: qwen3 returns a PlanDraft (the Builder checks the ids later)."""
    draft = OllamaAdapter().generate_plan(PROFILE, "Exactly 1 session with 2 exercises.", POOL)
    assert draft.sessions and draft.sessions[0].exercise_ids
