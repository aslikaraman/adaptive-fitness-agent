"""The LangChain coach agent: free text in, a structured Feedback out.

`LangChainCoachAgent` implements the CoachAgent interface (application layer) with a
tool-calling agent built by `langchain.agents.create_agent`. The agent can only act through
four tools:

    get_profile        - read the user's profile
    get_current_plan   - read the current training plan
    submit_feedback    - hand a Feedback to the adaptation pipeline
    undo_last_change   - take back the last adaptation

The plan changes only through submit_feedback, and submit_feedback only reaches the
adaptation pipeline, so the agent never decides a training change itself (FUNCTIONAL_FLOW.md
§0: the LLM handles language, our code handles logic).

The agent is only used for free-text input in the feedback and adaptation phases. It gets
one attempt, tool loop included: if it fails or does not submit, it raises LLMError and the
state falls back to the four fixed questions, which produce the same Feedback.
"""

from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_core.tools import tool

from fitness_agent.application.agent_context import AgentContext
from fitness_agent.application.coach_agent import CoachAgent
from fitness_agent.application.llm_client import LLMError
from fitness_agent.application.text import describe_plan
from fitness_agent.domain.models import KNOWN_REGIONS, Feedback
from fitness_agent.infrastructure.ollama_model import DEFAULT_MODEL, NUM_CTX, build_chat_model
from fitness_agent.infrastructure.prompts import AGENT_SYSTEM

NUM_PREDICT = 512
MAX_ITERATIONS = 6
# the graph takes two steps per tool round
RECURSION_LIMIT = 2 * MAX_ITERATIONS + 2

CONFIRMATION = "Thank you, I recorded your feedback."


@dataclass
class AgentRun:
    """What one agent run produced: the Feedback it submitted, if any."""

    feedback: Feedback | None = None
    report: str = ""


class LangChainCoachAgent(CoachAgent):
    """CoachAgent backed by a LangChain tool-calling agent on a local Ollama model."""

    def __init__(self, context: AgentContext, model: str = DEFAULT_MODEL,
                 num_ctx: int = NUM_CTX, chat_model=None) -> None:
        """Create the agent.

        chat_model can replace ChatOllama, e.g. with a stub in the tests.
        """
        self._context = context
        self._chat = chat_model or build_chat_model(model, num_predict=NUM_PREDICT,
                                                    num_ctx=num_ctx)

    def interpret(self, text: str, session_ref: str) -> Feedback:
        """Read the user's free text and return the Feedback the agent submitted.

        Raises LLMError when the model is unavailable or does not submit a valid Feedback,
        so the caller falls back to the fixed questions.
        """
        run = AgentRun()
        agent = create_agent(self._chat, self._tools(session_ref, run),
                             system_prompt=AGENT_SYSTEM)
        try:
            agent.invoke({"messages": [("human", text)]},
                         config={"recursion_limit": RECURSION_LIMIT})
        except Exception as error:  # pylint: disable=broad-exception-caught
            # LangChain, LangGraph, Ollama and httpx each raise their own types; the state
            # only needs to know that this attempt failed and why.
            raise LLMError(f"{type(error).__name__}: {error}") from error
        if run.feedback is None:
            raise LLMError(f"the agent did not submit feedback: {run.report or 'no tool call'}")
        return run.feedback

    # ------------------------------------------------------------------- the tools
    def _tools(self, session_ref: str, run: AgentRun) -> list[Any]:
        """The four tools of one run, closed over the session and the run's result."""
        context = self._context

        @tool
        def get_profile() -> str:
            """Return the user's profile: age, fitness level, goal, training days,
            equipment and injuries. Call this if you need to know who you are talking to."""
            profile = context.profile()
            return "No profile saved yet." if profile is None else profile.model_dump_json()

        @tool
        def get_current_plan() -> str:
            """Return the current training plan with its weeks, sessions and exercises
            (sets, reps and load). Call this if you need to know what the user trained."""
            plan = context.plan()
            return "No plan saved yet." if plan is None else describe_plan(plan)

        @tool
        def submit_feedback(difficulty: int, all_sets_done: bool, missed_sessions: int = 0,
                            pain_location: str | None = None) -> str:
            """Hand the user's feedback to the app. Call this exactly once, when you know
            how the session went; the app's own rules then decide what changes.

            difficulty: how hard the session felt, a whole number from 1 (very easy) to 10
            (could not finish). all_sets_done: did the user finish every set of the
            session? missed_sessions: how many planned sessions were skipped, 0 if none.
            pain_location: the region that hurt, if anything hurt - leave it out otherwise;
            one of knee, shoulder, lower_back, wrist, ankle, neck, hip.
            """
            feedback, problem = _read_feedback(session_ref, difficulty, all_sets_done,
                                               missed_sessions, pain_location)
            if problem is not None:
                return problem
            if context.submit is None:
                return "The app cannot record feedback at the moment."
            changes = context.submit(feedback)
            run.feedback = feedback
            run.report = "; ".join(changes) if changes else CONFIRMATION
            return run.report

        @tool
        def undo_last_change() -> str:
            """Take back the last change the app made to the plan. Only call this if the
            user asks for it."""
            if context.undo is None:
                return "There is no change that can be undone."
            return context.undo()

        return [get_profile, get_current_plan, submit_feedback, undo_last_change]


def _read_feedback(session_ref: str, difficulty: Any, all_sets_done: Any,
                   missed_sessions: Any, pain_location: Any) -> tuple[Feedback | None, str | None]:
    """Build the Feedback from the tool's arguments, or return the problem as text.

    The problem is given back to the model as the tool's result, so it can call the tool
    again with corrected arguments instead of failing the whole run.
    """
    if not isinstance(difficulty, int) or not 1 <= difficulty <= 10:
        return None, "difficulty must be a whole number from 1 to 10."
    if not isinstance(all_sets_done, bool):
        return None, "all_sets_done must be true or false."
    if not isinstance(missed_sessions, int) or not 0 <= missed_sessions <= 7:
        return None, "missed_sessions must be a whole number from 0 to 7."
    region = None
    if pain_location is not None:
        region = str(pain_location).strip().lower().replace(" ", "_")
        if region not in KNOWN_REGIONS:
            return None, ("pain_location must be one of " + ", ".join(KNOWN_REGIONS)
                          + ", or be left out if nothing hurt.")
    return Feedback(session_ref=session_ref, rpe=difficulty, pain=region is not None,
                    pain_region=region, all_sets_done=all_sets_done,
                    missed_sessions=missed_sessions), None
