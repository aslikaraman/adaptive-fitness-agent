"""Tests for the web chat UI: it only passes messages to CoachSession and shows the replies."""

import re

import gradio as gr

from fitness_agent.application.states import MENU, PlanReviewState
from fitness_agent.domain.plan import PlannedExercise
from fitness_agent.interface.plan_view import (HOW_IT_WORKS, current_week, dose, exercise_name,
                                               render_plan)
from fitness_agent.interface.web import (GOODBYE, MORE, QUICK_REPLIES, START_ERROR, Tab, answered,
                                         as_markdown, as_messages, build_demo, chat_once, opened,
                                         posted)
from tests.test_scenarios import STRENGTH, plan_for


class EchoSession:
    """Stands in for CoachSession: counts the starts, echoes the input, quits on "q"."""

    def __init__(self):
        """Not started, not finished, no plan."""
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
    """post() shows the message at once; answer() adds the reply once, then nothing more."""
    tab = Tab(EchoSession)
    history = tab.post("hi", [])
    assert history == [{"role": "user", "content": "hi"}]
    history = tab.answer(history)
    assert history[-1] == {"role": "assistant", "content": "echo hi"}
    assert tab.answer(history) == history


def test_quick_buttons_send_the_menu_choices_and_show_only_in_the_menu():
    """Every button value is a choice the plan menu offers."""
    for _, value in QUICK_REPLIES:
        assert re.search(rf"\b{value}\)", MENU)
    session = EchoSession()
    tab = Tab(lambda: session)
    assert not tab.menu_open()
    session.state = PlanReviewState()
    assert tab.menu_open()


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


# --------------------------------------------------------------------------- plan panel
def test_without_a_plan_the_panel_explains_the_steps():
    """No plan yet: the "How it works" card."""
    assert render_plan(None, None) == HOW_IT_WORKS


def test_the_panel_shows_progress_weeks_and_exercises():
    """Progress, the profile chips, all four weeks and readable exercise names."""
    plan = plan_for(STRENGTH)
    plan.weeks[0].sessions[0].status = "done"
    html = render_plan(plan, STRENGTH)
    total = sum(len(w.sessions) for w in plan.weeks)
    assert f"1 of {total} sessions done" in html
    assert all(f"Week {n}" in html for n in (1, 2, 3, 4))
    assert "💪 Strength" in html and "fa-done" in html
    first = plan.weeks[0].sessions[0].exercises[0].exercise_id
    assert exercise_name(first) in html


def test_the_current_week_is_the_first_with_a_planned_session():
    """Week 1 all done: week 2 is open."""
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


def test_the_page_events_lock_the_input_while_the_coach_answers():
    """Load shows the greeting; posting locks the box; the answer unlocks it."""
    tab = Tab(EchoSession)
    history, panel, _ = opened(tab)
    assert history[0]["content"] == "hello" and panel == HOW_IT_WORKS
    history, box, quick = posted("hi", history, tab)
    assert box["interactive"] is False and quick["visible"] is False
    history, _, box, _ = answered(history, tab)
    assert history[-1]["content"] == "echo hi" and box["interactive"] is True
