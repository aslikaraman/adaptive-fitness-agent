"""Plan Commands.

PlanCommand is a Template Method: execute() stores a Memento of the plan and
then calls _apply(), which each concrete Command (SwapExerciseCommand,
AdjustVolumeCommand, RescheduleCommand) implements. undo() restores the Memento.
"""

from abc import ABC, abstractmethod

from fitness_agent.domain.plan import PlanMemento, TrainingPlan


class PlanCommand(ABC):
    """A change to a TrainingPlan that can be undone."""

    def __init__(self, reason: str) -> None:
        """Create the command; reason names the rule that fired."""
        self.reason = reason
        self._plan: TrainingPlan | None = None
        self._memento: PlanMemento | None = None

    def execute(self, plan: TrainingPlan) -> None:
        """Store a Memento of the plan, then apply the change."""
        self._plan = plan
        self._memento = plan.create_memento(self.reason)
        self._apply(plan)

    def undo(self) -> None:
        """Restore the plan as it was before execute()."""
        if self._plan is None or self._memento is None:
            raise RuntimeError("undo() called before execute()")
        self._plan.restore(self._memento)

    @abstractmethod
    def _apply(self, plan: TrainingPlan) -> None:
        """Change the plan (implemented by each concrete Command)."""
