"""CoachSession: the Context of the State pattern and the only entry point for the CLI."""

from fitness_agent.application.adaptation import AdaptationService
from fitness_agent.application.coach_agent import CoachAgent
from fitness_agent.application.onboarding import OnboardingService
from fitness_agent.application.planning import PlanService
from fitness_agent.application.states import CoachState, OnboardingState, PlanReviewState
from fitness_agent.application.storage import Storage


class CoachSession:
    """Holds the current state and the user's data; the CLI passes every input line to it."""

    def __init__(self, onboarding: OnboardingService, planner: PlanService, storage: Storage,
                 adaptation: AdaptationService, agent: CoachAgent | None = None) -> None:
        """adaptation adapts the plan to a Feedback and undoes the last change."""
        self.onboarding = onboarding
        self.planner = planner
        self.storage = storage
        self.adaptation = adaptation
        self.agent = agent
        self.profile = storage.load_profile()
        self.plan = storage.load_plan()
        self.finished = False
        self._state: CoachState | None = None
        self._output: list[str] = []

    @property
    def state(self) -> CoachState | None:
        """The current state."""
        return self._state

    def start(self) -> str:
        """Begin with the saved plan, or with onboarding; return the text to show."""
        self._move_to(PlanReviewState() if self.plan is not None else OnboardingState())
        return self._flush()

    def handle(self, text: str) -> str:
        """Pass one line of input to the current state; return the text to show."""
        if self._state is None:
            raise RuntimeError("call start() first")
        self._move_to(self._state.handle(self, text.strip()))
        return self._flush()

    def say(self, text: str) -> None:
        """Queue text for the user."""
        self._output.append(text)

    def finish(self) -> None:
        """End the conversation."""
        self.finished = True

    def _move_to(self, state: CoachState) -> None:
        """Make state current and enter it; follow states that move on at once."""
        while state is not None and state is not self._state:
            self._state = state
            state = state.enter(self)

    def _flush(self) -> str:
        """Return and clear the queued text."""
        text, self._output = "\n".join(self._output), []
        return text
