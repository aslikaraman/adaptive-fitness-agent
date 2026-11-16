"""The CoachAgent interface: turns free-text feedback into a Feedback (implemented by the
LangChain agent)."""

from abc import ABC, abstractmethod

from fitness_agent.domain.models import Feedback


class CoachAgent(ABC):
    """Reads the user's free-text description of a session."""

    @abstractmethod
    def interpret(self, text: str, session_ref: str) -> Feedback:
        """Return the structured Feedback for the logged session.

        Raises LLMError when no valid Feedback comes out (the caller asks the fixed questions).
        """
