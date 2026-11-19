"""The thin web chat UI (interface layer) — the second view on the same CoachSession.

It does exactly what ``cli.py`` does, only over HTTP instead of a terminal:

* start the session once per browser tab and show what it says (``CoachSession.start()``);
* pass every message the user types, unchanged, to ``CoachSession.handle(text)``;
* show the reply.

So the interface layer still holds no ``UserProfile``, no ``TrainingPlan`` and no rules: the
*current state* of the State machine calls the application services (generate the plan,
submit feedback, undo the last change). That is why the CLI and the web UI can share one
session type — and why "parts should be exchangeable" is visible in the demo: the same
application and domain code runs behind two views (PATTERNS.md, *MVC*).

Gradio's own loading indicator covers the slow steps: a plan on the CPU with a local model
takes about 30-60 s, and the spinner is shown while ``handle()`` runs.

Run with:  python -m fitness_agent.interface.web        (then open http://localhost:7860)
"""

from collections.abc import Callable

import gradio as gr

from fitness_agent.application.session import CoachSession

TITLE = "Adaptive Fitness Agent (Design Patterns UE, Group 07)"
WELCOME = ("Type an answer and press Enter. Your answers rebuild the plan only through the "
           "adaptation pipeline, and every change can be undone.")
GOODBYE = "Bye."
MORE = "…"
PLACEHOLDER = "Type your answer ..."
START_ERROR = "The session could not be started. Please reload the page."

SessionFactory = Callable[[], CoachSession]
Message = dict


class Tab:
    """The session of one browser tab: built and started on the first message.

    A ``gr.State`` holds one of these per tab, so nothing in this module keeps a registry of
    users, and the composition root still decides what a session is built from.
    """

    def __init__(self, factory: SessionFactory) -> None:
        """Remember how to build the session; nothing is created yet."""
        self.factory = factory
        self.session: CoachSession | None = None

    def conversation(self) -> CoachSession:
        """The started session of this tab."""
        if self.session is None:
            self.session = self.factory()
            self.session.start()
        return self.session

    def send(self, message: str, history: list | None,
             request: gr.Request) -> tuple[list[Message], str]:  # pylint: disable=unused-argument
        """One user message in, the updated transcript and an empty box out."""
        if not message or not message.strip():
            return as_messages(history), ""
        return chat_once(self.conversation(), message.strip(), history), ""


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


def chat_once(session: CoachSession, message: str, history: list | None) -> list[Message]:
    """Add the user's message and the coach's reply to the chat history.

    This is the whole bridge between Gradio and the application: one message in, one reply
    out, exactly like one line in the CLI. Nothing here reads or changes the plan.
    """
    history = as_messages(history)
    history.append({"role": "user", "content": message})
    try:
        reply = session.handle(message)
    except RuntimeError:  # the session was not started (e.g. a fresh worker process)
        reply = START_ERROR
    history.append({"role": "assistant",
                    "content": reply or (GOODBYE if session.finished else MORE)})
    return history


def build_demo(session_factory: SessionFactory) -> gr.Blocks:
    """Build the chat page on top of a session factory.

    The factory is a callable so that Gradio can start a *new* conversation for a page load
    without this module choosing a concrete storage or adapter: the composition root
    (``main.py``) decides what a session is built from.
    """
    def respond(message: str, history: list | None, tab: Tab,
                request: gr.Request) -> tuple[list[Message], str]:
        """One user message in, the updated transcript and an empty box out."""
        return tab.send(message, history, request)

    with gr.Blocks(title=TITLE) as demo:
        tab = gr.State(Tab(session_factory))
        gr.Markdown(f"## {TITLE}\n{WELCOME}")
        transcript = gr.Chatbot(label="Coach", height=460)
        message = gr.Textbox(placeholder=PLACEHOLDER, label="Your answer", lines=2)
        send = gr.Button("Send", variant="primary")
        gr.Markdown("_Every input goes to `CoachSession.handle()`, the same call the CLI "
                    "makes. The slow LLM steps (about 30-60 s for a plan on the CPU) are "
                    "covered by the loading indicator._")

        for trigger in (message.submit,  # pylint: disable=no-member
                        send.click):  # pylint: disable=no-member
            trigger(respond, [message, transcript, tab], [transcript, message],
                    show_progress="full")

    return demo


def main(session_factory: SessionFactory | None = None, **launch: object) -> None:
    """Build the page (for a real session unless a factory is injected) and serve it."""
    if session_factory is None:  # imported here: the root imports the interface layer
        from fitness_agent.interface.main import build_session  # pylint: disable=import-outside-toplevel

        session_factory = build_session
    build_demo(session_factory).launch(**launch)


if __name__ == "__main__":  # pragma: no cover
    main()
