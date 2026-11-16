"""Tests for the LLMClient interface and FakeLLMClient."""

import pytest

from fitness_agent.application.llm_client import LLMClient, LLMError
from fitness_agent.domain.models import PlanDraft, UserProfile
from tests.fakes import FakeLLMClient

PROFILE = UserProfile(age=25, fitness_level="beginner", goal="strength", days_per_week=3)


def test_llm_client_cannot_be_instantiated():
    """LLMClient is an interface: a class must implement all four methods."""
    with pytest.raises(TypeError):
        LLMClient()  # pylint: disable=abstract-class-instantiated


def test_fake_returns_fixed_answers():
    """The fake returns what it was given and records the calls."""
    fake = FakeLLMClient(profile=PROFILE, plan_draft=PlanDraft(sessions=[]))
    assert fake.extract_profile("anything") == PROFILE
    assert fake.generate_plan(PROFILE, "", []) == PlanDraft(sessions=[])
    assert fake.explain_changes(["rule"]) == "Fake explanation."
    assert fake.calls == ["extract_profile", "generate_plan", "explain_changes"]


def test_fake_fails_the_first_n_calls():
    """failures = 2 makes two calls fail, the third succeeds."""
    fake = FakeLLMClient(profile=PROFILE, failures=2)
    for _ in range(2):
        with pytest.raises(LLMError):
            fake.extract_profile("anything")
    assert fake.extract_profile("anything") == PROFILE


def test_fake_can_fail_a_text_call():
    """A failing explain_changes() lets tests reach the template-text fallback."""
    fake = FakeLLMClient(failures=1)
    with pytest.raises(LLMError):
        fake.explain_changes(["rule"])
    assert fake.explain_changes(["rule"]) == "Fake explanation."
