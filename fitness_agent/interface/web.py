"""The thin web chat UI (interface layer): the second view on the same CoachSession.

It does exactly what ``cli.py`` does, only over HTTP instead of a terminal:

* start the session once per browser tab and show what it says (``CoachSession.start()``);
* pass every message the user types, unchanged, to ``CoachSession.handle(text)``;
* show the reply.

Next to the chat, a side panel shows the current plan (``plan_view.render_plan``). It only
reads ``session.plan`` and ``session.profile``; the quick buttons send the same "1", "2", "3"
that the menu asks for. So the interface layer still holds no rules: the *current state* of
the State machine calls the application services (generate the plan, submit feedback, undo
the last change). That is why the CLI and the web UI share one session type, and why
"parts should be exchangeable" is visible in the demo (PATTERNS.md, *MVC*).

A message is shown at once; the coach's reply follows in a second step, so the slow LLM
steps (about 1-2 minutes for a plan with a local model on the CPU) run behind a visible
"thinking" indicator while the input is locked.

Run with:  python -m fitness_agent.interface.web        (then open http://localhost:7860)
"""

from collections.abc import Callable
from pathlib import Path

import gradio as gr

from fitness_agent.application.session import CoachSession
from fitness_agent.application.states import PlanReviewState
from fitness_agent.interface.plan_view import render_plan

TITLE = "Adaptive Fitness Coach"
PAGE_TITLE = "Adaptive Fitness Coach · Design Patterns UE, Group 07"
HERO = f"""
<div class="fa-hero">
  <div class="fa-hero-icon">🏋️</div>
  <div>
    <h1>{TITLE}</h1>
    <p>A 4-week training plan that adapts after every workout, running on your own computer.</p>
    <div class="fa-chips">
      <span class="fa-chip">🧠 Local AI coach</span>
      <span class="fa-chip">🛡️ Safety rules first</span>
      <span class="fa-chip">↩️ Every change can be undone</span>
    </div>
  </div>
</div>
"""
HINT = ("Answer in your own words and press Enter. Building a plan with the local model "
        "takes 1-2 minutes.")
FOOTER = "Design Patterns UE · TU Graz · Group 07"
GOODBYE = "Bye. Great work, see you at the next session! 💪"
MORE = "…"
PLACEHOLDER = "Type your answer, e.g. “30”, “3 days a week” or “squats felt like 8/10”"
START_ERROR = "The session could not be started. Please reload the page."
# the menu choices of PlanReviewState (states.MENU), as one-click buttons
QUICK_REPLIES = (("📝 Log a workout", "1"), ("🗓️ New plan", "2"), ("↩️ Undo last change", "3"))

HERE = Path(__file__).parent
AVATARS = (str(HERE / "assets" / "user.svg"), str(HERE / "assets" / "coach.svg"))
CSS = (HERE / "style.css").read_text(encoding="utf-8")
THEME = gr.themes.Soft(primary_hue="orange", secondary_hue="amber", neutral_hue="slate",
                       font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"])

SessionFactory = Callable[[], CoachSession]
Message = dict


def as_markdown(text: str) -> str:
    """Keep the indentation of plain-text lines (Markdown would drop leading spaces)."""
    lines = []
    for line in text.split("\n"):
        stripped = line.lstrip(" ")
        lines.append(" " * (len(line) - len(stripped)) + stripped)
    return "\n".join(lines)


def as_messages(history: list | None) -> list[Message]:
    """Gradio sometimes keeps the plain (user, assistant) pairs: normalise them to messages."""
    messages: list[Message] = []
    for item in history or []:
        if isinstance(item, dict):
            messages.append(item)
        elif isinstance(item, (list, tuple)) and len(item) == 2:  # the old pair format
            messages.append({"role": "user", "content": item[0]})
            messages.append({"role": "assistant", "content": item[1]})
    return messages


def reply_to(session: CoachSession, message: str) -> str:
    """The coach's answer to one message, exactly like one line in the CLI."""
    try:
        reply = session.handle(message)
    except RuntimeError:  # the session was not started (e.g. a fresh worker process)
        return START_ERROR
    return as_markdown(reply) if reply else (GOODBYE if session.finished else MORE)


def chat_once(session: CoachSession, message: str, history: list | None) -> list[Message]:
    """Add the user's message and the coach's reply to the chat history.

    This is the whole bridge between Gradio and the application: one message in, one reply
    out. Nothing here reads or changes the plan.
    """
    history = as_messages(history)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply_to(session, message)})
    return history


class Tab:
    """The session of one browser tab: built and started when the page loads.

    A ``gr.State`` holds one of these per tab, so nothing in this module keeps a registry of
    users, and the composition root still decides what a session is built from.
    """

    def __init__(self, factory: SessionFactory) -> None:
        """Remember how to build the session; nothing is created yet."""
        self.factory = factory
        self.session: CoachSession | None = None
        self.greeting = ""
        self.pending = ""

    def conversation(self) -> CoachSession:
        """The started session of this tab."""
        if self.session is None:
            self.session = self.factory()
            self.greeting = self.session.start()
        return self.session

    def greet(self) -> list[Message]:
        """The transcript a new page starts with: the session's first words."""
        self.conversation()
        return [{"role": "assistant", "content": as_markdown(self.greeting)}]

    def menu_open(self) -> bool:
        """The quick buttons fit only while the plan menu waits for a choice."""
        session = self.conversation()
        return isinstance(session.state, PlanReviewState) and not session.finished

    def post(self, message: str, history: list | None) -> list[Message]:
        """Step 1: show the user's message at once and remember it for the reply."""
        history = as_messages(history)
        self.pending = (message or "").strip()
        if self.pending:
            history.append({"role": "user", "content": self.pending})
        return history

    def answer(self, history: list | None) -> list[Message]:
        """Step 2: the coach's reply to the remembered message (the slow part)."""
        history = as_messages(history)
        if self.pending:
            message, self.pending = self.pending, ""
            history.append({"role": "assistant",
                            "content": reply_to(self.conversation(), message)})
        return history

    def send(self, message: str, history: list | None) -> list[Message]:
        """Both steps in one call (used by the tests and by any non-streaming caller)."""
        return self.answer(self.post(message, history))

    def plan_html(self) -> str:
        """The side panel for the current plan."""
        session = self.conversation()
        return render_plan(session.plan, session.profile)


def opened(tab: Tab):
    """Page load: start the session, show its first words and the plan."""
    return tab.greet(), tab.plan_html(), gr.update(visible=tab.menu_open())


def posted(message: str, history: list | None, tab: Tab):
    """Show the message, empty and lock the input, hide the quick buttons."""
    return (tab.post(message, history), gr.update(value="", interactive=False),
            gr.update(visible=False))


def answered(history: list | None, tab: Tab):
    """Show the reply, refresh the plan, unlock the input."""
    history = tab.answer(history)
    finished = tab.conversation().finished
    return (history, tab.plan_html(), gr.update(interactive=not finished),
            gr.update(visible=tab.menu_open()))


def build_demo(session_factory: SessionFactory) -> gr.Blocks:
    """Build the chat page on top of a session factory.

    The factory is a callable so that Gradio can start a *new* conversation for a page load
    without this module choosing a concrete storage or adapter: the composition root
    (``main.py``) decides what a session is built from.
    """
    with gr.Blocks(title=PAGE_TITLE, fill_height=True) as demo:
        tab = gr.State(Tab(session_factory))
        gr.HTML(HERO)
        with gr.Row(equal_height=False):
            with gr.Column(scale=3):
                transcript = gr.Chatbot(show_label=False, height=560, avatar_images=AVATARS,
                                        placeholder="Warming up …", layout="bubble",
                                        elem_classes="fa-chat")
                with gr.Row(visible=False, elem_classes="fa-quick") as quick:
                    buttons = [(gr.Button(label, size="sm", variant="secondary"), value)
                               for label, value in QUICK_REPLIES]
                with gr.Row():
                    message = gr.Textbox(placeholder=PLACEHOLDER, show_label=False, lines=1,
                                         max_lines=4, scale=5, autofocus=True,
                                         elem_classes="fa-input")
                    send = gr.Button("Send ➤", variant="primary", scale=1,
                                     elem_classes="fa-send")
                gr.Markdown(HINT, elem_classes="fa-hint")
            with gr.Column(scale=2):
                panel = gr.HTML()
        gr.Markdown(FOOTER, elem_classes="fa-hint")

        demo.load(opened, [tab], [transcript, panel, quick])  # pylint: disable=no-member
        reply = {"fn": answered, "inputs": [transcript, tab],
                 "outputs": [transcript, panel, message, quick], "show_progress": "minimal"}
        for trigger in (message.submit,  # pylint: disable=no-member
                        send.click):  # pylint: disable=no-member
            trigger(posted, [message, transcript, tab], [transcript, message, quick],
                    show_progress="hidden").then(**reply)
        for button, value in buttons:
            button.click(lambda history, tab, value=value: posted(value, history, tab),
                         [transcript, tab], [transcript, message, quick],
                         show_progress="hidden").then(**reply)

    return demo


def main(session_factory: SessionFactory | None = None, **launch: object) -> None:
    """Build the page (for a real session unless a factory is injected) and serve it."""
    if session_factory is None:  # imported here: the root imports the interface layer
        from fitness_agent.interface.main import build_session  # pylint: disable=import-outside-toplevel

        session_factory = build_session
    build_demo(session_factory).launch(theme=THEME, css=CSS, **launch)


if __name__ == "__main__":  # pragma: no cover
    main()
