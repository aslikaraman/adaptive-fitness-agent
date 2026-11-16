"""PlanService: plan generation with the LLM retry loop (FUNCTIONAL_FLOW.md §4).

The LLM chooses the exercises of week 1; the Strategy sets the training numbers; the Builder
assembles and validates the plan. Schema errors (LLMError) and Builder violations
(PlanValidationError) share one budget of 3 attempts. After that, the Strategy builds the plan
without the LLM.
"""

from fitness_agent.application.catalog_loader import CatalogLoader
from fitness_agent.application.llm_client import LLMClient, LLMError
from fitness_agent.application.retry import with_retries
from fitness_agent.application.storage import Storage
from fitness_agent.domain.builder import PlanValidationError, TrainingPlanBuilder
from fitness_agent.domain.catalog import allowed_pool
from fitness_agent.domain.models import Exercise, PlanDraft, UserProfile
from fitness_agent.domain.plan import TrainingPlan
from fitness_agent.domain.strategies import PlanningStrategy, StrategyFactory


class PlanService:
    """Creates, explains and saves the TrainingPlan for a profile."""

    def __init__(self, llm: LLMClient, catalog: CatalogLoader, storage: Storage,
                 strategies: StrategyFactory, builder_class=TrainingPlanBuilder) -> None:
        """builder_class can be replaced in tests; the composition root uses the default."""
        self._llm = llm
        self._catalog = catalog.load()
        self._storage = storage
        self._strategies = strategies
        self._builder_class = builder_class

    def generate(self, profile: UserProfile) -> TrainingPlan:
        """Create the plan (LLM draft, else fallback), add the coach summary and save it."""
        strategy = self._strategies.create(profile)
        pool = allowed_pool(self._catalog, profile)
        constraints = strategy.constraints(profile)

        def attempt(previous_error: str | None) -> TrainingPlan:
            """One LLM draft, built and validated."""
            draft = self._llm.generate_plan(profile, constraints, pool, previous_error)
            return self._build_from_draft(draft, strategy, profile, pool)

        plan = with_retries(attempt, (LLMError, PlanValidationError))
        if plan is None:
            plan = self._build_fallback(strategy, profile, pool)
        plan.coach_summary = self._summary(profile, plan)
        self._storage.save_plan(plan)
        return plan

    def _new_builder(self, strategy: PlanningStrategy, profile: UserProfile,
                     pool: list[Exercise]):
        """A fresh builder for one attempt."""
        return self._builder_class(self._catalog, pool, strategy, profile)

    def _build_from_draft(self, draft: PlanDraft, strategy: PlanningStrategy,
                          profile: UserProfile, pool: list[Exercise]) -> TrainingPlan:
        """Direct the Builder with the LLM's choice and the Strategy's numbers."""
        days = strategy.session_days(profile)
        if len(draft.sessions) != len(days):
            raise PlanValidationError(f"expected {len(days)} sessions, got {len(draft.sessions)}")
        by_id = {exercise.id: exercise for exercise in self._catalog}
        builder = self._new_builder(strategy, profile, pool)
        builder.start_week(1)
        for day, session in zip(days, draft.sessions):
            builder.add_session(day, session.focus)
            for exercise_id in session.exercise_ids:
                if exercise_id not in by_id:
                    raise PlanValidationError(f"unknown exercise id {exercise_id}")
                numbers = strategy.prescribe(by_id[exercise_id], profile)
                builder.add_exercise(exercise_id, numbers.sets, numbers.reps, numbers.load,
                                     numbers.rest_s)
        strategy.add_progression_weeks(builder, profile)
        return builder.build()

    def _build_fallback(self, strategy: PlanningStrategy, profile: UserProfile,
                        pool: list[Exercise]) -> TrainingPlan:
        """Let the Strategy build the plan without the LLM."""
        builder = self._new_builder(strategy, profile, pool)
        strategy.add_fallback_week(builder, profile, pool)
        strategy.add_progression_weeks(builder, profile)
        plan = builder.build()
        plan.llm_generated = False
        return plan

    def _summary(self, profile: UserProfile, plan: TrainingPlan) -> str:
        """The LLM's explanation (1 attempt), else a template; plus notes the user must see."""
        try:
            summary = self._llm.summarize_plan(profile, plan)
        except LLMError:
            sessions = len(plan.weeks[0].sessions) if plan.weeks else 0
            summary = (f"This {profile.goal.replace('_', ' ')} plan has {sessions} sessions "
                       f"per week for 4 weeks.")
        if profile.minor:
            summary += " Because you are under 18, the volume is kept low."
        if profile.injury_notes:
            summary += (" About your other limitations (" + "; ".join(profile.injury_notes)
                        + "): please see a doctor or physiotherapist if you are unsure.")
        return summary
