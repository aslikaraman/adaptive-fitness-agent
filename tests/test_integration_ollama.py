"""Integration tests against the local Ollama model (qwen3).

They are skipped by default; run them with:  pytest -m ollama
Ollama must be running, and on a CPU each test takes one to two minutes.
"""

import pytest

from fitness_agent.application.agent_context import AgentContext
from fitness_agent.application.planning import PlanService
from fitness_agent.domain.catalog import allowed_pool
from fitness_agent.domain.models import UserProfile
from fitness_agent.domain.strategies import StrategyFactory
from fitness_agent.infrastructure.coach_agent_langchain import LangChainCoachAgent
from fitness_agent.infrastructure.json_catalog_loader import JsonCatalogLoader
from fitness_agent.infrastructure.ollama_adapter import OllamaAdapter
from tests.fakes import InMemoryStorage

pytestmark = pytest.mark.ollama

PROFILE = UserProfile(age=30, fitness_level="intermediate", goal="strength", days_per_week=3,
                      equipment=["dumbbells", "barbell"])


def test_real_plan_generation_gives_a_valid_four_week_plan():
    """qwen3 chooses the exercises (or the fallback takes over); the plan always passes the gate."""
    catalog = JsonCatalogLoader()
    plan = PlanService(OllamaAdapter(), catalog, InMemoryStorage(PROFILE),
                       StrategyFactory()).generate(PROFILE)
    pool = {exercise.id for exercise in allowed_pool(catalog.load(), PROFILE)}
    assert len(plan.weeks) == 4 and len(plan.weeks[0].sessions) == 3
    assert all(e.exercise_id in pool for w in plan.weeks for s in w.sessions for e in s.exercises)
    assert plan.coach_summary


def test_real_agent_turns_free_text_into_feedback():
    """qwen3 calls submit_feedback with the right values for a clear description."""
    agent = LangChainCoachAgent(AgentContext(InMemoryStorage(PROFILE)))
    feedback = agent.interpret("Squats were brutal, about an 8 out of 10, my knee hurt a bit, "
                               "but I finished all sets and didn't skip anything.", "w1d5")
    assert feedback.pain and feedback.pain_region == "knee"
    assert feedback.all_sets_done and feedback.missed_sessions == 0
    assert 7 <= feedback.rpe <= 9
