"""The thin web chat UI (interface layer): the second view on the same CoachSession.

It does exactly what ``cli.py`` does, only over HTTP instead of a terminal:

* start the session once per browser tab and show what it says (``CoachSession.start()``);
* pass every message the user types, unchanged, to ``CoachSession.handle(text)``;
* show the reply.

Next to the chat, a side panel shows the current plan, one tab per week (``plan_view``). It
only reads ``session.plan`` and ``session.profile``; the quick buttons send the same "1", "2",
"3", "q" that the menu asks for, and "Undo" is shown only while there is a change to undo. At
the menu, the chat shows the coach's news but not the typed menu and the plan text again: the
buttons and the panel show those (``for_buttons``). So the
interface layer still holds no rules: the *current state* of the State machine calls the
application services (generate the plan, submit feedback, undo the last change). That is why
the CLI and the web UI share one session type, and why "parts should be exchangeable" is
visible in the demo (PATTERNS.md, *MVC*).

A message is shown at once together with a "Coach is thinking" bubble with a spinner; the
reply replaces the bubble in a second step. So the slow LLM steps (about 1-2 minutes for a
plan with a local model on the CPU) are visible in the chat itself, while the input and the
Send button are locked.

Run with:  python -m fitness_agent.interface.web        (then open http://localhost:7860)
"""

from collections.abc import Callable
from pathlib import Path

import gradio as gr

from fitness_agent.application.session import CoachSession
from fitness_agent.application.states import (CHOOSE_AGAIN, MENU, OnboardingState,
                                              PlanReviewState)
from fitness_agent.application.text import describe_plan
from fitness_agent.domain.plan import TrainingPlan
from fitness_agent.interface.plan_view import (NEW_PROFILE, WEEKS, current_week, render_header,
                                               render_week)

TITLE = "Adaptive Fitness Coach"
PAGE_TITLE = "Adaptive Fitness Coach · Design Patterns UE, Group 07"
HERO = f"""
<div class="fa-hero">
  <div class="fa-hero-icon">🏋️</div>
  <div>
    <h1>{TITLE}</h1>
    <p>A 4-week training plan that adapts after every workout.</p>
    <div class="fa-chips">
      <span class="fa-chip fa-tip" tabindex="0" data-tip="A language model (qwen3 via Ollama) reads
        your answers in your own words and explains the plan. It never decides the numbers.">
        Local AI coach</span>
      <span class="fa-chip fa-tip" tabindex="0" data-tip="Fixed rules decide every change:
        exercises that strain an injury are left out, and pain never raises a load.">
        Safety rules first</span>
      <span class="fa-chip fa-tip" tabindex="0" data-tip="After you log a workout, press
        &quot;Undo last change&quot; to get the plan back exactly as it was before.">
        Every change can be undone</span>
    </div>
  </div>
</div>
"""
HINT = ("Answer in your own words and press Enter. Building a plan with the local model "
        "takes 1-2 minutes.")
FOOTER = "Design Patterns UE · TU Graz · Group 07"
GOODBYE = "Bye. Great work, see you at the next session! 💪"
MORE = "…"
PLACEHOLDER = "Type your answer …"
# shown in the empty chat for the moment the session needs to start
WELCOME_CARD = """<div class="fa-welcome">
<div class="fa-welcome-icon">🏋️</div>
<h3>Hi, I'm your fitness coach</h3>
<p>I'll ask you a few short questions, then build your 4-week plan.<br>
After each workout, tell me how it went and I'll adapt the plan.</p>
<div class="fa-dots"><span></span><span></span><span></span></div>
</div>"""
START_ERROR = "The session could not be started. Please reload the page."
SEND, SENDING = "Send", "Working …"
# shown with a spinner while the coach answers; replaced by the reply
THINKING = {"role": "assistant",
            "content": "Reading your answer. Building or adapting a plan with the local model "
                       "can take 1-2 minutes, so stay with me.",
            "metadata": {"title": "🏋️ Coach is thinking …", "status": "pending"}}

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
AVATARS = (str(ASSETS / "user.svg"), str(ASSETS / "coach.svg"))
# the menu choices of PlanReviewState (states.MENU) as one-click buttons: (label, input, icon)
LOG, NEW_PLAN, UNDO, QUIT = (("Log a workout", "1", str(ASSETS / "log.svg")),
                             ("New plan", "2", str(ASSETS / "plan.svg")),
                             ("Undo last change", "3", str(ASSETS / "undo.svg")),
                             ("Quit", "q", str(ASSETS / "quit.svg")))
QUICK_REPLIES = (LOG, NEW_PLAN, UNDO, QUIT)
PLAN_NOTE = ("📋 Your plan is in the panel on the right: open a week to see each day. "
             "What next? Choose a button below.")
PICK_A_BUTTON = "Please choose one of the buttons below."
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
        lines.append("\u00a0" * (len(line) - len(stripped)) + stripped)
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
    return reply or (GOODBYE if session.finished else MORE)


def for_buttons(text: str, plan: TrainingPlan | None) -> str:
    """The web view of a menu reply: the buttons replace the typed menu, and the panel
    replaces the plan text (the CLI still shows both as text)."""
    if plan is not None:
        text = text.replace(describe_plan(plan), PLAN_NOTE)
    text = text.replace(CHOOSE_AGAIN + MENU, PICK_A_BUTTON).replace(MENU, "")
    return text.strip() or PLAN_NOTE


def chat_once(session: CoachSession, message: str, history: list | None) -> list[Message]:
    """Add the user's message and the coach's reply to the chat history.

    This is the whole bridge between Gradio and the application: one message in, one reply
    out. Nothing here reads or changes the plan.
    """
    history = as_messages(history)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": as_markdown(reply_to(session, message))})
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
        return [{"role": "assistant", "content": as_markdown(self.shown(self.greeting))}]

    def menu_open(self) -> bool:
        """The quick buttons fit only while the plan menu waits for a choice."""
        session = self.conversation()
        return isinstance(session.state, PlanReviewState) and not session.finished

    def can_undo(self) -> bool:
        """There is a feedback cycle of this session that can be undone."""
        return bool(self.conversation().adaptation.history())

    def post(self, message: str, history: list | None) -> list[Message]:
        """Step 1: show the user's message and the "thinking" bubble at once; remember the
        message for the reply."""
        history = as_messages(history)
        self.pending = (message or "").strip()
        if self.pending:
            history.append({"role": "user", "content": self.pending})
            history.append(dict(THINKING))
        return history

    def answer(self, history: list | None) -> list[Message]:
        """Step 2: the coach's reply to the remembered message (the slow part)."""
        history = as_messages(history)
        if self.pending:
            message, self.pending = self.pending, ""
            if history and history[-1].get("role") == "assistant":
                history.pop()  # the "thinking" bubble that post() added
            was_menu = self.menu_open()
            reply = reply_to(self.conversation(), message)
            if was_menu and self.onboarding():
                history = []  # "New plan": a fresh conversation, the old plan text goes away
            history.append({"role": "assistant", "content": as_markdown(self.shown(reply))})
        return history

    def shown(self, text: str) -> str:
        """What the chat shows of the coach's text: at the menu, buttons and panel replace the
        typed menu and the plan text."""
        return for_buttons(text, self.conversation().plan) if self.menu_open() else text

    def onboarding(self) -> bool:
        """The user is (re)doing the onboarding, so the old plan no longer applies."""
        return isinstance(self.conversation().state, OnboardingState)

    def send(self, message: str, history: list | None) -> list[Message]:
        """Both steps in one call (used by the tests and by any non-streaming caller)."""
        return self.answer(self.post(message, history))

    def controls(self) -> tuple:
        """Visibility of the quick-button row and of the undo button."""
        menu = self.menu_open()
        return gr.update(visible=menu), gr.update(visible=menu and self.can_undo())

    def panel(self) -> tuple:
        """The side panel: header, the week tabs (on the current week) and one HTML per week."""
        session = self.conversation()
        if self.onboarding():  # a new profile is being set up: hide the old plan
            header, plan = (NEW_PROFILE if session.plan else render_header(None, None)), None
        else:
            plan = session.plan
            header = render_header(plan, session.profile)
        tabs = gr.update(visible=bool(plan and plan.weeks),
                         selected=current_week(plan) if plan and plan.weeks else 1)
        return (header, tabs, *(render_week(plan, n) for n in range(1, WEEKS + 1)))


def opened(tab: Tab) -> tuple:
    """Page load: start the session, show its first words, the buttons and the plan."""
    return (tab.greet(), *tab.controls(), *tab.panel())


def posted(message: str, history: list | None, tab: Tab) -> tuple:
    """Show the message, empty and lock the input, mark the button busy, hide the quick
    buttons."""
    return (tab.post(message, history), gr.update(value="", interactive=False),
            gr.update(value=SENDING, interactive=False), gr.update(visible=False))


def answered(history: list | None, tab: Tab) -> tuple:
    """Show the reply, unlock the input, refresh the buttons and the plan."""
    history = tab.answer(history)
    finished = tab.conversation().finished
    return (history, gr.update(interactive=not finished),
            gr.update(value=SEND, interactive=not finished), *tab.controls(), *tab.panel())


def _chat_column() -> tuple:
    """The chat, the quick buttons ({input: button}) and the message box with Send."""
    transcript = gr.Chatbot(show_label=False, height=540, avatar_images=AVATARS,
                            placeholder=WELCOME_CARD, layout="bubble", buttons=["copy"],
                            feedback_options=None, elem_classes="fa-chat")
    with gr.Row(visible=False, elem_classes="fa-quick") as quick:
        buttons = {value: gr.Button(label, icon=icon, size="sm", variant="secondary",
                                    elem_classes="fa-pill")
                   for label, value, icon in QUICK_REPLIES}
    with gr.Row(equal_height=False, elem_classes="fa-composer"):
        message = gr.Textbox(placeholder=PLACEHOLDER, show_label=False, lines=1, max_lines=4,
                             scale=6, container=False, autofocus=True, elem_classes="fa-input")
        send = gr.Button(SEND, variant="primary", scale=1, min_width=110, elem_classes="fa-send")
    gr.Markdown(HINT, elem_classes="fa-hint")
    return transcript, quick, buttons, message, send


def _plan_column() -> list:
    """The plan panel: the header and one tab per week (the order of Tab.panel())."""
    header = gr.HTML()
    with gr.Tabs(visible=False, elem_classes="fa-weeks") as weeks:
        week_html = []
        for number in range(1, WEEKS + 1):
            with gr.Tab(f"Week {number}", id=number):
                week_html.append(gr.HTML())
    return [header, weeks, *week_html]


def build_demo(session_factory: SessionFactory) -> gr.Blocks:
    """Build the chat page on top of a session factory.

    The factory is a callable so that Gradio can start a *new* conversation for a page load
    without this module choosing a concrete storage or adapter: the composition root
    (``main.py``) decides what a session is built from.
    """
    with gr.Blocks(title=PAGE_TITLE) as demo:
        tab = gr.State(Tab(session_factory))
        gr.HTML(HERO, elem_classes="fa-hero-wrap")
        with gr.Row(equal_height=False, elem_classes="fa-main"):
            with gr.Column(scale=3):
                transcript, quick, buttons, message, send = _chat_column()
            with gr.Column(scale=2, elem_classes="fa-side"):
                side = _plan_column()
        gr.Markdown(FOOTER, elem_classes="fa-hint fa-footer")

        controls = [quick, buttons[UNDO[1]]]
        demo.load(opened, [tab], [transcript, *controls, *side],  # pylint: disable=no-member
                  show_progress="hidden")
        reply = {"fn": answered, "inputs": [transcript, tab], "show_progress": "hidden",
                 "outputs": [transcript, message, send, *controls, *side]}
        lock = [transcript, message, send, quick]
        for trigger in (message.submit,  # pylint: disable=no-member
                        send.click):  # pylint: disable=no-member
            trigger(posted, [message, transcript, tab], lock,
                    show_progress="hidden").then(**reply)
        for value, button in buttons.items():
            button.click(lambda history, tab, value=value: posted(value, history, tab),
                         [transcript, tab], lock, show_progress="hidden").then(**reply)

    return demo


def main(session_factory: SessionFactory | None = None, **launch: object) -> None:
    """Build the page (for a real session unless a factory is injected) and serve it."""
    if session_factory is None:  # imported here: the root imports the interface layer
        from fitness_agent.interface.main import build_session  # pylint: disable=import-outside-toplevel

        session_factory = build_session
    build_demo(session_factory).launch(theme=THEME, css=CSS, footer_links=[], **launch)


if __name__ == "__main__":  # pragma: no cover
    main()
