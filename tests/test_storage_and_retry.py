"""Tests for JsonStorage, JsonCatalogLoader and the retry loop."""

import pytest

from fitness_agent.application.llm_client import LLMError
from fitness_agent.application.retry import with_retries
from fitness_agent.domain.models import Feedback, UserProfile
from fitness_agent.domain.plan import TrainingPlan, Week
from fitness_agent.infrastructure.json_catalog_loader import JsonCatalogLoader
from fitness_agent.infrastructure.json_storage import JsonStorage

PROFILE = UserProfile(age=25, fitness_level="beginner", goal="strength", days_per_week=3)


def test_json_storage_round_trip(tmp_path):
    """What is saved is loaded back unchanged; feedback is appended."""
    storage = JsonStorage(tmp_path / "data")
    assert storage.load_profile() is None and storage.load_plan() is None
    assert storage.load_feedbacks() == []
    plan = TrainingPlan(weeks=[Week(number=1)], coach_summary="hi")
    feedback = Feedback(session_ref="w1d1", rpe=6, pain=False, all_sets_done=True)
    storage.save_profile(PROFILE)
    storage.save_plan(plan)
    storage.save_feedback(feedback)
    storage.save_feedback(feedback)
    assert storage.load_profile() == PROFILE
    assert storage.load_plan() == plan
    assert storage.load_feedbacks() == [feedback, feedback]


def test_json_catalog_loader_reads_the_catalog():
    """The default path is resources/exercise_catalog.json."""
    catalog = JsonCatalogLoader().load()
    assert len(catalog) == 50 and catalog[0].id == "bw_squat"


def test_retry_passes_the_previous_error_and_succeeds():
    """The third attempt gets the second attempt's error and succeeds."""
    seen = []

    def attempt(previous_error):
        """Fail twice, then succeed."""
        seen.append(previous_error)
        if len(seen) < 3:
            raise LLMError(f"error {len(seen)}")
        return "ok"

    assert with_retries(attempt, (LLMError,)) == "ok"
    assert seen == [None, "error 1", "error 2"]


def test_retry_returns_none_after_three_failures():
    """After 3 failed attempts the caller gets None and uses its fallback."""
    calls = []

    def attempt(_previous_error):
        """Always fail."""
        calls.append(1)
        raise LLMError("always")

    assert with_retries(attempt, (LLMError,)) is None
    assert len(calls) == 3


def test_retry_does_not_hide_bugs():
    """Errors that are not listed are raised, not retried."""
    def attempt(_previous_error):
        """Raise an error that is not retried."""
        raise KeyError("bug")

    with pytest.raises(KeyError):
        with_retries(attempt, (LLMError,))
