"""Tests for the CLI, the composition root and the coach agent's tools (no Ollama needed)."""

from fitness_agent.application.adaptation import NOTHING_TO_UNDO, AdaptationService
from fitness_agent.application.agent_context import AgentContext
from fitness_agent.application.session import CoachSession
from fitness_agent.domain.models import UserProfile
from fitness_agent.infrastructure.coach_agent_langchain import LangChainCoachAgent, _read_feedback
from fitness_agent.infrastructure.json_catalog_loader import JsonCatalogLoader
from fitness_agent.interface.cli import GOODBYE, WELCOME, Cli
from fitness_agent.interface.main import build_session
from tests.fakes import InMemoryStorage

PROFILE = UserProfile(age=30, fitness_level="beginner", goal="strength", days_per_week=3)


class ScriptedSession:
    """Stands in for CoachSession: answers every line with "echo: <line>", quits on "q"."""

    finished = False

    def start(self):
        """The first text."""
        return "hello"

    def handle(self, text):
        """Echo, or finish on q."""
        if text == "q":
            self.finished = True
            return ""
        return f"echo: {text}"


def test_cli_passes_every_line_to_the_session_until_it_finishes():
    """The CLI only shows what the session says and reads input."""
    lines, shown = iter(["one", "q"]), []
    Cli(ScriptedSession(), reader=lambda: next(lines), writer=shown.append).run()
    assert shown == [WELCOME, "hello", "echo: one", GOODBYE]


def test_cli_stops_on_end_of_input():
    """Ctrl-D (EOFError) ends the conversation."""
    def reader():
        """No more input."""
        raise EOFError

    shown = []
    Cli(ScriptedSession(), reader=reader, writer=shown.append).run()
    assert shown[-1] == GOODBYE


def test_composition_root_builds_a_session(tmp_path):
    """build_session wires every layer; nothing contacts Ollama until a model call."""
    session = build_session(str(tmp_path))
    assert isinstance(session, CoachSession)
    assert "How old are you?" in session.start()


def test_read_feedback_checks_the_tool_arguments():
    """Invalid arguments come back to the model as text; valid ones become a Feedback."""
    assert _read_feedback("w1d1", 11, True, 0, None)[1].startswith("difficulty")
    assert "pain_location" in _read_feedback("w1d1", 5, True, 0, "elbow")[1]
    feedback, problem = _read_feedback("w1d1", 7, False, 1, "Lower back")
    assert problem is None and feedback.pain_region == "lower_back" and feedback.pain


def test_agent_tools_read_submit_and_undo():
    """The tools read the data, record the Feedback and undo through the context."""
    storage = InMemoryStorage(PROFILE)
    service = AdaptationService(storage, JsonCatalogLoader())
    agent = LangChainCoachAgent(AgentContext(storage, undo=service.undo_last_change),
                                chat_model=object())
    run = type("Run", (), {"feedback": None, "report": ""})()
    get_profile, get_plan, submit, undo = agent._tools("w1d1", run)  # pylint: disable=protected-access
    assert '"goal":"strength"' in get_profile.invoke({})
    assert get_plan.invoke({}) == "No plan saved yet."
    reply = submit.invoke({"difficulty": 4, "all_sets_done": True})
    assert reply == "Thank you, I recorded your feedback."
    assert run.feedback.rpe == 4 and run.feedback.session_ref == "w1d1"
    assert undo.invoke({}) == NOTHING_TO_UNDO


def test_the_explanation_gets_the_full_facts_but_not_the_warning():
    """The LLM explains from the filters' messages, so it cannot guess the reason."""
    from fitness_agent.application.planning import PlanService  # pylint: disable=import-outside-toplevel
    from fitness_agent.domain.models import Feedback  # pylint: disable=import-outside-toplevel
    from fitness_agent.domain.strategies import StrategyFactory  # pylint: disable=import-outside-toplevel
    from tests.fakes import FakeLLMClient  # pylint: disable=import-outside-toplevel

    class RecordingLLM(FakeLLMClient):
        """Records the facts it is asked to explain."""

        def explain_changes(self, changes):
            """Keep the facts."""
            self.facts = changes  # pylint: disable=attribute-defined-outside-init
            return "Explained."

    profile = UserProfile(age=30, fitness_level="intermediate", goal="strength",
                          days_per_week=3, equipment=["barbell", "dumbbells"])
    storage = InMemoryStorage(profile)
    PlanService(FakeLLMClient(failures=99), JsonCatalogLoader(), storage,
                StrategyFactory()).generate(profile)
    llm = RecordingLLM()
    feedback = Feedback(session_ref="w1d5", rpe=6, pain=True, pain_region="knee",
                        all_sets_done=True)
    messages = AdaptationService(storage, JsonCatalogLoader(), llm=llm).adapt(feedback)
    assert messages[-1] == "Explained."
    assert any("removed from the remaining sessions" in fact for fact in llm.facts)
    assert not any("does not diagnose" in fact for fact in llm.facts)
