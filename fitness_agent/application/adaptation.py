"""AdaptationService: runs the adaptation pipeline and executes its Commands (FUNCTIONAL_FLOW §6).

The filters only decide; this service executes the Commands they emitted, in order, as one
history entry (one feedback cycle), saves the plan and explains the change. "Undo last
change" undoes the Commands of the last entry in reverse order. If executing fails half-way,
the Commands already executed are undone, so the plan is never left half-changed.
"""

from fitness_agent.application.catalog_loader import CatalogLoader
from fitness_agent.application.llm_client import LLMClient, LLMError
from fitness_agent.application.storage import Storage
from fitness_agent.domain.adaptation import (COULD_NOT_ADAPT, AdaptationContext,
                                             AdaptationPipeline, default_pipeline)
from fitness_agent.domain.catalog import allowed_pool
from fitness_agent.domain.commands import PlanCommand
from fitness_agent.domain.models import Feedback
from fitness_agent.domain.plan import TrainingPlan
from fitness_agent.domain.strategies import StrategyFactory

NO_PLAN = "There is no plan yet. Finish the onboarding first."
NOTHING_TO_UNDO = "There is no change that can be undone."
SESSION_DONE = "session done"


class AdaptationService:
    """Adapts the plan to one Feedback, keeps the history and undoes the last cycle."""

    def __init__(self, storage: Storage, catalog: CatalogLoader,
                 pipeline: AdaptationPipeline | None = None, llm: LLMClient | None = None,
                 strategies: StrategyFactory | None = None) -> None:
        """pipeline defaults to SafetyFilter -> ScheduleFilter -> LoadFilter; without an llm
        the explanation is a template."""
        self._storage = storage
        self._catalog = catalog.load()
        self._pipeline = pipeline or default_pipeline()
        self._llm = llm
        self._strategies = strategies or StrategyFactory()
        self._history: list[tuple[TrainingPlan, list[PlanCommand]]] = []

    def adapt(self, feedback: Feedback) -> list[str]:
        """Adapt the saved plan to the feedback; return the lines to show the user."""
        plan = self._storage.load_plan()
        profile = self._storage.load_profile()
        if plan is None or profile is None:
            return [NO_PLAN]
        context = self._pipeline.run(AdaptationContext(
            feedback=feedback, plan=plan, profile=profile, catalog=self._catalog,
            pool=allowed_pool(self._catalog, profile),
            previous_feedback=self._previous(feedback),
            strategy=self._strategies.create(profile)))
        if context.failed:
            return context.messages
        if not self._execute(plan, context.commands):
            return [*context.messages, COULD_NOT_ADAPT]
        self._history.append((plan, context.commands))
        self._storage.save_plan(plan)
        changes = [c.reason for c in context.commands if c.reason != SESSION_DONE]
        return context.messages + ([self._explain(changes)] if changes else [])

    def undo_last_change(self) -> str:
        """Undo the last feedback cycle; return what was undone."""
        if not self._history:
            return NOTHING_TO_UNDO
        plan, commands = self._history.pop()
        for command in reversed(commands):
            command.undo()
        self._storage.save_plan(plan)
        changes = [c.reason for c in commands if c.reason != SESSION_DONE]
        undone = "; ".join(changes) if changes else "the session was marked as not done"
        return "Undone: " + undone

    def history(self) -> list[str]:
        """One line per feedback cycle, oldest first: the rules that fired."""
        return ["; ".join(c.reason for c in commands) for _, commands in self._history]

    def _previous(self, feedback: Feedback) -> Feedback | None:
        """The last saved Feedback before this one (the state saves this one first)."""
        saved = self._storage.load_feedbacks()
        if saved and saved[-1] == feedback:
            saved = saved[:-1]
        return saved[-1] if saved else None

    @staticmethod
    def _execute(plan: TrainingPlan, commands: list[PlanCommand]) -> bool:
        """Execute every Command; on an error undo the executed ones and report False."""
        done: list[PlanCommand] = []
        try:
            for command in commands:
                command.execute(plan)
                done.append(command)
        except (ValueError, KeyError, IndexError):
            for command in reversed(done):
                command.undo()
            return False
        return True

    def _explain(self, changes: list[str]) -> str:
        """The LLM's two sentences (1 attempt), else a template naming the rules."""
        if self._llm is not None:
            try:
                return self._llm.explain_changes(changes)
            except LLMError:
                pass
        return "Changed: " + "; ".join(changes) + "."
