"""Tests for the web chat UI: it only passes messages to CoachSession and shows the replies."""

import gradio as gr

from fitness_agent.interface.web import (GOODBYE, MORE, START_ERROR, Tab, as_messages, build_demo,
                                         chat_once)


class EchoSession:
    """Stands in for CoachSession: counts the starts, echoes the input, quits on "q"."""

    def __init__(self):
        """Not started, not finished."""
        self.starts = 0
        self.finished = False

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
    """No text: "…" while the session runs, "Bye." when it is finished."""
    session = EchoSession()
    assert chat_once(session, "!", [])[-1]["content"] == MORE
    assert chat_once(session, "q", [])[-1]["content"] == GOODBYE


def test_old_pair_history_is_converted():
    """Gradio's old (user, assistant) pairs become messages."""
    assert as_messages([("a", "b")]) == [{"role": "user", "content": "a"},
                                         {"role": "assistant", "content": "b"}]


def test_tab_starts_its_session_once_and_ignores_empty_messages():
    """One session per browser tab, started on the first message."""
    session = EchoSession()
    tab = Tab(lambda: session)
    history, box = tab.send("  ", [], None)
    assert (history, box, session.starts) == ([], "", 0)
    tab.send("hi", [], None)
    tab.send("again", [], None)
    assert session.starts == 1


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
