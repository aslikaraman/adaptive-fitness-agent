"""Tests for the web chat UI: it only passes messages to CoachSession and shows the replies."""

import re

import gradio as gr

from fitness_agent.application.states import MENU, PlanReviewState
from fitness_agent.domain.plan import PlannedExercise
from fitness_agent.interface.plan_view import (HOW_IT_WORKS, NEW_PROFILE, current_week, dose,
                                               exercise_name, render_header, render_week)
from fitness_agent.interface.web import (GOODBYE, MORE, QUICK_REPLIES, SEND, SENDING, START_ERROR,
                                         THINKING, Tab, answered, as_markdown, as_messages,
                                         PICK_A_BUTTON, PLAN_NOTE, build_demo, chat_once,
                                         for_buttons, opened, posted)
from tests.fakes import InMemoryStorage
from tests.test_scenarios import STRENGTH, plan_for
from tests.test_session import PROFILE, make_plan, make_session


class History:
    """Stands in for AdaptationService: only the history of feedback cycles."""

    def __init__(self):
        """No cycle yet."""
        self.cycles = []

    def history(self):
        """One entry per cycle."""
        return self.cycles


class EchoSession:
    """Stands in for CoachSession: counts the starts, echoes the input, quits on "q"."""

    def __init__(self):
        """Not started, not finished, no plan."""
        self.adaptation = History()
        self.starts = 0
        self.finished = False
        self.state = None
        self.plan = None
        self.profile = None

    def start(self):
        """Count the start."""
        self.starts += 1
        return "hello"

    def handle(self, text):
        """Echo the text; "q" finishes; "!" says nothing."""
        if text == "q":
            self.finished = True
            return ""
        return "" if text == "!" else f"echo {text}"


def test_chat_once_adds_the_message_and_the_reply():
    """One message in, one reply out, exactly like one line in the CLI."""
    history = chat_once(EchoSession(), "yes", [])
    assert history == [{"role": "user", "content": "yes"},
                       {"role": "assistant", "content": "echo yes"}]


def test_empty_reply_and_finished_session():
    """No text: "…" while the session runs, the goodbye when it is finished."""
    session = EchoSession()
    assert chat_once(session, "!", [])[-1]["content"] == MORE
    assert chat_once(session, "q", [])[-1]["content"] == GOODBYE


def test_old_pair_history_is_converted():
    """Gradio's old (user, assistant) pairs become messages."""
    assert as_messages([("a", "b")]) == [{"role": "user", "content": "a"},
                                         {"role": "assistant", "content": "b"}]


def test_indentation_survives_markdown():
    """Leading spaces of the plan text become non-breaking spaces."""
    assert as_markdown("Week 1\n  Day 1") == "Week 1\n  Day 1"


def test_the_greeting_is_shown_when_the_page_opens():
    """The first question is visible before the user types anything."""
    session = EchoSession()
    tab = Tab(lambda: session)
    assert tab.greet() == [{"role": "assistant", "content": "hello"}]
    assert session.starts == 1


def test_tab_starts_its_session_once_and_ignores_empty_messages():
    """One session per browser tab; an empty message changes nothing."""
    session = EchoSession()
    tab = Tab(lambda: session)
    assert not tab.send("  ", [])
    tab.send("hi", [])
    assert tab.send("again", []) == [{"role": "user", "content": "again"},
                                     {"role": "assistant", "content": "echo again"}]
    assert session.starts == 1


def test_the_reply_comes_in_a_second_step():
    """post() shows the message and the thinking bubble at once; answer() replaces the bubble
    with the reply once, then adds nothing more."""
    tab = Tab(EchoSession)
    history = tab.post("hi", [])
    assert history == [{"role": "user", "content": "hi"}, THINKING]
    assert history[-1]["metadata"]["status"] == "pending"
    history = tab.answer(history)
    assert history == [{"role": "user", "content": "hi"},
                       {"role": "assistant", "content": "echo hi"}]
    assert tab.answer(history) == history


def test_quick_buttons_send_the_menu_choices_and_show_only_in_the_menu():
    """Every button value is a choice the plan menu offers."""
    for _, value, _ in QUICK_REPLIES:
        assert re.search(rf"\b{value}\)", MENU)
    session = EchoSession()
    tab = Tab(lambda: session)
    assert [c["visible"] for c in tab.controls()] == [False, False]
    session.state = PlanReviewState()
    assert [c["visible"] for c in tab.controls()] == [True, False]


def test_undo_is_offered_only_when_there_is_something_to_undo():
    """Before the first feedback cycle the undo button stays hidden."""
    session = EchoSession()
    session.state = PlanReviewState()
    tab = Tab(lambda: session)
    assert not tab.can_undo()
    session.adaptation.cycles.append("too easy")
    assert tab.can_undo() and tab.controls()[1]["visible"]


def test_unstarted_session_shows_a_start_error():
    """A session that was not started gives a clear message instead of a crash."""
    class Unstarted(EchoSession):
        """handle() before start()."""

        def handle(self, text):
            """Like CoachSession without start()."""
            raise RuntimeError("call start() first")

    assert chat_once(Unstarted(), "hi", [])[-1]["content"] == START_ERROR


def test_build_demo_returns_a_gradio_page():
    """The page is built on a session factory; nothing is started yet."""
    session = EchoSession()
    assert isinstance(build_demo(lambda: session), gr.Blocks)
    assert session.starts == 0


def test_the_page_events_lock_the_input_while_the_coach_answers():
    """Load shows the greeting; posting locks the box; the answer unlocks it."""
    tab = Tab(EchoSession)
    history, _, _, panel, *_ = opened(tab)
    assert history[0]["content"] == "hello" and panel == HOW_IT_WORKS
    history, box, button, quick = posted("hi", history, tab)
    assert box["interactive"] is False and quick["visible"] is False
    assert (button["value"], button["interactive"]) == (SENDING, False)
    history, box, button, *_ = answered(history, tab)
    assert history[-1]["content"] == "echo hi" and box["interactive"] is True
    assert (button["value"], button["interactive"]) == (SEND, True)


# --------------------------------------------------------------------------- plan panel
def test_without_a_plan_the_panel_explains_the_steps():
    """No plan yet: the "How it works" card and no week tabs."""
    assert render_header(None, None) == HOW_IT_WORKS
    header, tabs, *weeks = Tab(EchoSession).panel()
    assert header == HOW_IT_WORKS and tabs["visible"] is False and weeks == [""] * 4


def test_the_panel_shows_progress_and_each_week_its_days():
    """Progress and profile on top; each week tab lists its days with readable names."""
    plan = plan_for(STRENGTH)
    plan.weeks[0].sessions[0].status = "done"
    header = render_header(plan, STRENGTH)
    total = sum(len(w.sessions) for w in plan.weeks)
    assert f"1 of {total} sessions done" in header and "💪 Strength" in header
    week = render_week(plan, 1)
    assert "1 of 3 sessions done · this is your current week" in week and "fa-done" in week
    first = plan.weeks[0].sessions[0].exercises[0].exercise_id
    assert exercise_name(first) in week
    assert "current week" not in render_week(plan, 2) and render_week(plan, 5) == ""


def test_the_panel_opens_on_the_current_week():
    """The week tabs are shown and the current week is selected."""
    session = EchoSession()
    session.plan = plan_for(STRENGTH)
    for day in session.plan.weeks[0].sessions:
        day.status = "done"
    _, tabs, *weeks = Tab(lambda: session).panel()
    assert (tabs["visible"], tabs["selected"]) == (True, 2) and len(weeks) == 4


def test_the_current_week_is_the_first_with_a_planned_session():
    """Week 1 all done: week 2 is current."""
    plan = plan_for(STRENGTH)
    assert current_week(plan) == 1
    for session in plan.weeks[0].sessions:
        session.status = "done"
    assert current_week(plan) == 2


def test_dose_for_each_load_type():
    """kg, time and bodyweight read naturally."""
    def exercise(load_type, load):
        """One planned exercise."""
        return PlannedExercise(exercise_id="x", load_type=load_type, sets=3, reps=8, load=load,
                               rest_s=60)

    assert dose(exercise("kg", 12.5)) == "3 × 8 · 12.5 kg"
    assert dose(exercise("time", 30)) == "3 × 30 s"
    assert dose(exercise("bw", 0)) == "3 × 8 · bodyweight"
    assert exercise_name("goblet_squat") == "Goblet squat"


def test_new_plan_clears_the_chat_and_hides_the_old_plan_until_the_new_one_is_ready():
    """"New plan": a fresh chat with the first question, the old plan leaves the panel, and the
    new plan and profile appear when the onboarding is done."""
    session, _ = make_session(InMemoryStorage(PROFILE, make_plan()))
    tab = Tab(lambda: session)
    history = tab.greet()
    assert tab.panel()[1]["visible"] is True
    history = tab.answer(tab.post("2", history))
    assert len(history) == 1 and "How old are you?" in history[0]["content"]
    header, tabs, *_ = tab.panel()
    assert header == NEW_PROFILE and tabs["visible"] is False
    for text in ("25", "beginner", "strength", "3", "dumbbells", "no", "yes"):
        history = tab.answer(tab.post(text, history))
    header, tabs, *_ = tab.panel()
    assert "Your training plan" in header and "Beginner" in header and tabs["visible"] is True
    assert len(history) > 2  # onboarding answers are not cleared


def test_at_the_menu_the_buttons_and_the_panel_replace_menu_and_plan_text():
    """The chat shows the coach's news, not the typed menu or the whole plan again."""
    session, _ = make_session(InMemoryStorage(PROFILE, make_plan()))
    tab = Tab(lambda: session)
    greeting = tab.greet()[0]["content"]
    assert greeting == PLAN_NOTE and "1) Give feedback" not in greeting
    assert tab.send("5", [])[-1]["content"] == PICK_A_BUTTON
    undone = tab.send("3", [])[-1]["content"]
    assert undone.startswith("Undone: test change") and "1) Give feedback" not in undone
    assert "push_up" not in undone and PLAN_NOTE in undone


def test_the_cli_text_is_unchanged_outside_the_menu():
    """Questions are shown as they are; only menu replies are shortened."""
    assert for_buttons("How old are you?", None) == "How old are you?"
    assert chat_once(EchoSession(), "hi", [])[-1]["content"] == "echo hi"
