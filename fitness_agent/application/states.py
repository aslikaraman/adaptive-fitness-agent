"""The states of the coach conversation (State pattern, FUNCTIONAL_FLOW.md §3-§6).

Each state handles one line of user input and returns the next state, so the states make the
transitions themselves; CoachSession only stores and calls the current one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fitness_agent.application.llm_client import LLMError
from fitness_agent.application.text import describe_plan
from fitness_agent.domain.models import GOALS, KNOWN_REGIONS, LEVELS, Feedback, UserProfile

if TYPE_CHECKING:
    from fitness_agent.application.session import CoachSession


class CoachState(ABC):
    """One phase of the conversation."""

    def enter(self, session: CoachSession) -> CoachState | None:  # pylint: disable=unused-argument
        """Run when the state becomes current; may return a state to move on to at once."""
        return None

    @abstractmethod
    def handle(self, session: CoachSession, text: str) -> CoachState:
        """Handle one line of user input and return the next state (self to stay)."""


@dataclass
class Question:
    """A question and the function that turns the answer into a value (ValueError = re-ask)."""

    key: str
    text: str
    parse: Callable[[str], Any] = str


class AskingState(CoachState):
    """Asks a queue of questions and re-asks after an invalid answer (Template Method).

    Subclasses fill the queue in prepare(), may add questions in after_answer(), and decide the
    next state in finish().
    """

    def __init__(self) -> None:
        """Start with no questions and no answers."""
        self._queue: deque[Question] = deque()
        self.answers: dict[str, Any] = {}

    def enter(self, session: CoachSession) -> CoachState | None:
        """Prepare the questions and ask the first one."""
        follow = self.prepare(session)
        if follow is None:
            session.say(self._queue[0].text)
        return follow

    def handle(self, session: CoachSession, text: str) -> CoachState:
        """Store a valid answer and ask the next question; when none is left, finish."""
        question = self._queue[0]
        try:
            value = question.parse(text)
        except ValueError as error:
            session.say(f"{error} {question.text}")
            return self
        self._queue.popleft()
        self.answers[question.key] = value
        self.after_answer(session, question.key, value)
        next_state = self if self._queue else self.finish(session)
        if next_state is self:
            session.say(self._queue[0].text)
        return next_state

    def ask_next(self, *questions: Question) -> None:
        """Put questions at the front of the queue."""
        self._queue.extendleft(reversed(questions))

    def ask_later(self, *questions: Question) -> None:
        """Put questions at the end of the queue."""
        self._queue.extend(questions)

    @abstractmethod
    def prepare(self, session: CoachSession) -> CoachState | None:
        """Fill the queue; return a state instead to skip this one."""

    def after_answer(self, session: CoachSession, key: str, value: Any) -> None:
        """React to one answer, e.g. by adding a follow-up question."""

    @abstractmethod
    def finish(self, session: CoachSession) -> CoachState:
        """All questions are answered: return the next state (self after adding questions)."""


# --------------------------------------------------------------------------- answer parsers
def _integer(low: int, high: int) -> Callable[[str], int]:
    """A parser for a whole number from low to high."""
    def parse(text: str) -> int:
        """Return the number, or raise ValueError with a hint."""
        try:
            value = int(text)
        except ValueError:
            value = low - 1
        if not low <= value <= high:
            raise ValueError(f"Please enter a whole number from {low} to {high}.")
        return value
    return parse


def _choice(options: tuple[str, ...]) -> Callable[[str], str]:
    """A parser for one of the options (spaces may replace underscores)."""
    def parse(text: str) -> str:
        """Return the option, or raise ValueError listing the options."""
        value = text.strip().lower().replace(" ", "_")
        if value not in options:
            raise ValueError("Please answer with one of: " + ", ".join(options) + ".")
        return value
    return parse


def _yes_no(text: str) -> bool:
    """A parser for yes/no."""
    value = text.strip().lower()
    if value in ("y", "yes"):
        return True
    if value in ("n", "no"):
        return False
    raise ValueError("Please answer yes or no.")


def _comma_list(text: str) -> list[str]:
    """A parser for a comma-separated list (empty or "none" means no items)."""
    if text.strip().lower() in ("", "none", "no"):
        return []
    return [item.strip().lower().replace(" ", "_") for item in text.split(",") if item.strip()]


ONBOARDING_QUESTIONS = (
    Question("age", "How old are you?"),
    Question("fitness_level", "What is your fitness level (beginner, intermediate, advanced)?"),
    Question("goal", "What is your goal (strength, fat loss, endurance)?"),
    Question("days_per_week", "How many days per week can you train?"),
    Question("equipment", "What equipment do you have?"),
    Question("injuries", "Do you have any injuries or limitations?"),
)

FIXED_ONBOARDING_QUESTIONS = (
    Question("age", "Age (14-90)?", _integer(14, 90)),
    Question("fitness_level", "Fitness level (beginner, intermediate, advanced)?", _choice(LEVELS)),
    Question("goal", "Goal (strength, fat_loss, endurance)?", _choice(GOALS)),
    Question("days_per_week", "Days per week (1-7)?", _integer(1, 7)),
    Question("equipment", "Equipment, comma separated (bodyweight, dumbbells, barbell, "
                          "kettlebell, bands, pullup_bar, machines)?", _comma_list),
    Question("injuries", "Injured regions, comma separated (knee, shoulder, lower_back, wrist, "
                         "ankle, neck, hip), or none?", _comma_list),
)


class OnboardingState(AskingState):
    """F1: the six onboarding questions, read by the LLM; fixed questions as the fallback."""

    def __init__(self) -> None:
        """Start in free-text mode."""
        super().__init__()
        self._fixed = False

    def prepare(self, session: CoachSession) -> CoachState | None:
        """Ask the six free-text questions."""
        session.say("Let's set up your profile.")
        self.ask_later(*ONBOARDING_QUESTIONS)

    def finish(self, session: CoachSession) -> CoachState:
        """Read the answers with the LLM; if that fails, switch to the fixed questions."""
        if not self._fixed:
            answers = "\n".join(f"{q.text} {self.answers[q.key]}" for q in ONBOARDING_QUESTIONS)
            profile = session.onboarding.extract(answers)
            if profile is None:
                self._fixed = True
                session.say("I could not read all answers. Please answer a few short questions.")
                self.ask_later(*FIXED_ONBOARDING_QUESTIONS)
                return self
        else:
            profile = UserProfile(**{**self.answers, "injuries": [
                {"region": region} for region in self.answers["injuries"]]})
        session.onboarding.save(profile)
        session.profile = profile
        session.say("Creating your plan. This can take a minute.")
        session.plan = session.planner.generate(profile)
        return PlanReviewState()


MENU = "What next? 1) Give feedback  2) New plan (redo onboarding)  3) Undo last change  q) Quit"


class PlanReviewState(CoachState):
    """Shows the plan and the menu."""

    def enter(self, session: CoachSession) -> CoachState | None:
        """Show the current plan (as saved) and the menu."""
        session.plan = session.storage.load_plan() or session.plan
        session.say(describe_plan(session.plan))
        session.say(MENU)

    def handle(self, session: CoachSession, text: str) -> CoachState:
        """1 -> feedback, 2 -> onboarding again, 3 -> undo, q -> quit."""
        choice = text.strip().lower()
        if choice == "1":
            return FeedbackState()
        if choice == "2":
            return OnboardingState()
        if choice == "3":
            session.say(session.adaptation.undo_last_change())
            return PlanReviewState()
        if choice == "q":
            session.finish()
            return self
        session.say("Please choose 1, 2, 3 or q. " + MENU)
        return self


class FeedbackState(AskingState):
    """F3: which session was done, then free text for the agent or the four fixed questions."""

    def __init__(self) -> None:
        """No session chosen yet."""
        super().__init__()
        self._session_ref = ""
        self._planned_sets = 0
        self._choices: list[tuple[int, Any]] = []

    def prepare(self, session: CoachSession) -> CoachState | None:
        """Offer the next planned sessions; if none is left, go back to the plan."""
        self._choices = [(week.number, s) for week in session.plan.weeks
                         for s in week.sessions if s.status == "planned"][:7]
        if not self._choices:
            session.say("All sessions are done. Choose 2 for a new plan.")
            return PlanReviewState()
        options = "  ".join(f"{i}) week {w} day {s.day_of_week} ({s.focus})"
                            for i, (w, s) in enumerate(self._choices, start=1))
        self.ask_later(Question("session", f"Which session did you do? {options}",
                                _integer(1, len(self._choices))))
        return None

    def after_answer(self, session: CoachSession, key: str, value: Any) -> None:
        """Add the follow-up questions that the answers call for."""
        if key == "session":
            week, chosen = self._choices[value - 1]
            self._session_ref = f"w{week}d{chosen.day_of_week}"
            self._planned_sets = sum(exercise.sets for exercise in chosen.exercises)
            if session.agent is not None:
                self.ask_next(Question("text", "How did it go? Describe it in your own words.",
                                       lambda text: self._interpret(session, text)))
            else:
                self.ask_next(*self._fixed_questions())
        elif key == "text" and value is None:
            session.say("I could not understand that. Four short questions:")
            self.ask_next(*self._fixed_questions())
        elif key == "pain" and value:
            self.ask_next(Question("pain_region", "Which region (knee, shoulder, lower_back, "
                                                  "wrist, ankle, neck, hip)?",
                                   _choice(KNOWN_REGIONS)))
        elif key == "all_sets_done" and not value:
            self.ask_next(Question("completed_sets", "How many sets did you complete?",
                                   _integer(0, self._planned_sets)))

    def _interpret(self, session: CoachSession, text: str) -> Feedback | None:
        """The agent's Feedback, or None if it failed (then the fixed questions follow)."""
        try:
            return session.agent.interpret(text, self._session_ref)
        except LLMError:
            return None

    @staticmethod
    def _fixed_questions() -> tuple[Question, ...]:
        """The four fixed feedback questions (follow-ups are added by after_answer)."""
        return (Question("rpe", "How hard was it (1-10)?", _integer(1, 10)),
                Question("pain", "Did anything hurt (yes/no)?", _yes_no),
                Question("all_sets_done", "Did you complete all sets (yes/no)?", _yes_no),
                Question("missed_sessions", "How many planned sessions did you miss?",
                         _integer(0, 7)))

    def finish(self, session: CoachSession) -> CoachState:
        """Build and save the Feedback, then adapt the plan."""
        feedback = self.answers.get("text")
        if feedback is None:
            feedback = Feedback(
                session_ref=self._session_ref, rpe=self.answers["rpe"], pain=self.answers["pain"],
                pain_region=self.answers.get("pain_region"),
                all_sets_done=self.answers["all_sets_done"],
                completed_sets=self.answers.get("completed_sets"),
                missed_sessions=self.answers["missed_sessions"])
        session.storage.save_feedback(feedback)
        return AdaptationState(feedback)


class AdaptationState(CoachState):
    """F4: hands the Feedback to the adaptation and shows the result, then the plan."""

    def __init__(self, feedback: Feedback) -> None:
        """The feedback to adapt the plan to."""
        self.feedback = feedback

    def enter(self, session: CoachSession) -> CoachState | None:
        """Adapt the plan, show the messages, then move on to the plan review."""
        for line in session.adaptation.adapt(self.feedback):
            session.say(line)
        return PlanReviewState()

    def handle(self, session: CoachSession, text: str) -> CoachState:
        """Not reached: this state moves on as soon as it is entered."""
        return PlanReviewState()
