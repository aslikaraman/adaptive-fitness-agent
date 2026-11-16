"""Test doubles shared by both halves of the project."""

from fitness_agent.application.catalog_loader import CatalogLoader
from fitness_agent.application.coach_agent import CoachAgent
from fitness_agent.application.llm_client import LLMClient, LLMError
from fitness_agent.application.storage import Storage
from fitness_agent.domain.builder import PlanValidationError
from fitness_agent.domain.models import Exercise, Feedback, PlanDraft, UserProfile
from fitness_agent.domain.plan import PlannedExercise, Session, TrainingPlan, Week
from fitness_agent.domain.strategies import PlanningStrategy, Prescription


class FakeLLMClient(LLMClient):
    """Returns fixed answers, so tests run without Ollama.

    failures = n makes the first n calls raise LLMError, to test the retry
    and the fallbacks (deterministic result or template text).
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
        self.previous_errors: list[str | None] = []

    def _answer(self, name: str, result):
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
        self.previous_errors.append(previous_error)
        return self._answer("extract_profile", self.profile)

    def generate_plan(
        self,
        profile: UserProfile,
        constraints: str,
        allowed_pool: list[Exercise],
        previous_error: str | None = None,
    ) -> PlanDraft:
        """Return the fixed plan draft."""
        self.previous_errors.append(previous_error)
        return self._answer("generate_plan", self.plan_draft)

    def summarize_plan(self, profile: UserProfile, plan: TrainingPlan) -> str:
        """Return the fixed summary."""
        return self._answer("summarize_plan", self.summary)

    def explain_changes(self, changes: list[str]) -> str:
        """Return the fixed explanation."""
        return self._answer("explain_changes", self.explanation)


class InMemoryStorage(Storage):
    """Keeps the data in memory instead of JSON files."""

    def __init__(self, profile: UserProfile | None = None, plan: TrainingPlan | None = None):
        """Optionally start with a saved profile and plan."""
        self.profile = profile
        self.plan = plan
        self.feedbacks: list[Feedback] = []

    def save_profile(self, profile: UserProfile) -> None:
        """Keep the profile."""
        self.profile = profile

    def load_profile(self) -> UserProfile | None:
        """Return the kept profile."""
        return self.profile

    def save_plan(self, plan: TrainingPlan) -> None:
        """Keep the plan."""
        self.plan = plan

    def load_plan(self) -> TrainingPlan | None:
        """Return the kept plan."""
        return self.plan

    def save_feedback(self, feedback: Feedback) -> None:
        """Keep the feedback."""
        self.feedbacks.append(feedback)

    def load_feedbacks(self) -> list[Feedback]:
        """Return the kept feedback."""
        return list(self.feedbacks)


class ListCatalogLoader(CatalogLoader):
    """Returns a given list of exercises."""

    def __init__(self, exercises: list[Exercise]) -> None:
        """The catalog to return."""
        self.exercises = exercises

    def load(self) -> list[Exercise]:
        """Return the catalog."""
        return list(self.exercises)


class FakeStrategy(PlanningStrategy):
    """Two sessions per week, fixed numbers, a simple fallback and no progression."""

    def session_days(self, profile: UserProfile) -> list[int]:
        """Days 1 and 4."""
        return [1, 4]

    def constraints(self, profile: UserProfile) -> str:
        """A fixed skeleton text."""
        return "Exactly 2 sessions."

    def prescribe(self, exercise: Exercise, profile: UserProfile) -> Prescription:
        """3 x 10, 20 kg for weights, 60 s rest."""
        return Prescription(sets=3, reps=10, load=20 if exercise.load_type == "kg" else 0,
                            rest_s=60)

    def weekly_set_limits(self, profile: UserProfile) -> tuple[int, int]:
        """Between 1 and 40 sets."""
        return 1, 40

    def add_fallback_week(self, builder, profile: UserProfile, pool: list[Exercise]) -> None:
        """Week 1 with the first pool exercise in both sessions."""
        builder.start_week(1)
        for day in self.session_days(profile):
            builder.add_session(day, "fallback")
            numbers = self.prescribe(pool[0], profile)
            builder.add_exercise(pool[0].id, numbers.sets, numbers.reps, numbers.load,
                                 numbers.rest_s)

    def add_progression_weeks(self, builder, profile: UserProfile) -> None:
        """No progression in the fake."""
        del builder, profile


class FakeStrategyFactory:
    """Always returns the same Strategy."""

    def __init__(self, strategy: PlanningStrategy | None = None) -> None:
        """The Strategy to return (a FakeStrategy by default)."""
        self.strategy = strategy or FakeStrategy()

    def create(self, profile: UserProfile) -> PlanningStrategy:
        """Return the Strategy, whatever the profile."""
        del profile
        return self.strategy


class SimpleBuilder:
    """A small working builder for the tests: checks that every exercise is in the pool.

    rejections = n makes the first n builds fail with PlanValidationError.
    """

    rejections = 0

    def __init__(self, catalog, allowed_pool, strategy, profile) -> None:
        """Same constructor as TrainingPlanBuilder."""
        self.load_types = {exercise.id: exercise.load_type for exercise in catalog}
        self.allowed = {exercise.id for exercise in allowed_pool}
        self.plan = TrainingPlan()
        del strategy, profile

    def start_week(self, number: int) -> None:
        """Start a week."""
        self.plan.weeks.append(Week(number=number))

    def add_session(self, day_of_week: int, focus: str) -> None:
        """Add a session."""
        self.plan.weeks[-1].sessions.append(Session(day_of_week=day_of_week, focus=focus))

    def add_exercise(self, exercise_id, sets, reps, load, rest_s) -> None:
        """Add an exercise."""
        self.plan.weeks[-1].sessions[-1].exercises.append(PlannedExercise(
            exercise_id=exercise_id, load_type=self.load_types[exercise_id], sets=sets,
            reps=reps, load=load, rest_s=rest_s))

    def build(self) -> TrainingPlan:
        """Reject while rejections > 0 or if an exercise is outside the pool."""
        if SimpleBuilder.rejections > 0:
            SimpleBuilder.rejections -= 1
            raise PlanValidationError("fake rejection")
        for week in self.plan.weeks:
            for session in week.sessions:
                for exercise in session.exercises:
                    if exercise.exercise_id not in self.allowed:
                        raise PlanValidationError(f"{exercise.exercise_id} is not allowed")
        return self.plan


class FakeAgent(CoachAgent):
    """Returns a fixed Feedback, or raises LLMError if none is given."""

    def __init__(self, feedback: Feedback | None = None) -> None:
        """The Feedback to return (with the session_ref of the call)."""
        self.feedback = feedback

    def interpret(self, text: str, session_ref: str) -> Feedback:
        """Return the fixed Feedback for this session, or fail."""
        if self.feedback is None:
            raise LLMError("fake agent failure")
        return self.feedback.model_copy(update={"session_ref": session_ref})
