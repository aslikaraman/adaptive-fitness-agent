"""The thin command-line interface (interface layer, ARCHITECTURE.md "Layers").

The CLI knows exactly three things:

* start the session and show what it says (``CoachSession.start()``);
* read one line and hand it, unchanged, to the session (``CoachSession.handle(line)``);
* stop when the session says it is finished, or when the user presses Ctrl-D / Ctrl-C.

Everything else is the State machine's business: the *current state* calls the application
services (generate plan, submit feedback, undo last change) and decides what the user is
asked next. So the interface layer holds no ``UserProfile``, no ``TrainingPlan`` and no
rules - it only shows state and reads input. A new menu option is a new state in
``application/states.py``, not a new branch here (ARCHITECTURE.md, "Where to put new code").

The reader and the writer are injected, so the CLI can be driven by a script in the tests
instead of a terminal.
"""

from collections.abc import Callable

from fitness_agent.application.session import CoachSession

PROMPT = "> "
WELCOME = "Adaptive Fitness Agent (Design Patterns UE, Group 07). Ctrl-D or Ctrl-C to quit."
GOODBYE = "Bye."


def read_line() -> str:
    """The default reader: one line from the terminal."""
    return input(PROMPT)


def write_line(text: str) -> None:
    """The default writer: one block of text to the terminal."""
    print(text)


class Cli:
    """One terminal conversation: shows what the coach says, reads what the user types."""

    def __init__(self, session: CoachSession, reader: Callable[[], str] = read_line,
                 writer: Callable[[str], None] = write_line) -> None:
        """reader returns one line (or raises EOFError); writer shows one block of text."""
        self.session = session
        self._reader = reader
        self._writer = writer

    def run(self) -> None:
        """Start the session and keep passing input to it until it is finished."""
        self._show(WELCOME)
        self._show(self.session.start())
        while not self.session.finished:
            try:
                line = self._reader()
            except (EOFError, KeyboardInterrupt):
                break
            self._show(self.session.handle(line))
        self._show(GOODBYE)

    def _show(self, text: str) -> None:
        """Write one block of text, unless there is nothing to say."""
        if text:
            self._writer(text)
