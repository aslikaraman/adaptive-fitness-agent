"""Tests for the agent run itself (LangChainCoachAgent.interpret) without Ollama.

A fake chat model plays the LLM: it returns scripted messages, including tool calls, so the
real LangChain agent loop runs and calls our tools.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from fitness_agent.application.agent_context import AgentContext
from fitness_agent.application.llm_client import LLMError
from fitness_agent.infrastructure.coach_agent_langchain import LangChainCoachAgent
from tests.fakes import InMemoryStorage


class ScriptedChat(GenericFakeChatModel):
    """A fake chat model that accepts tools, so create_agent() can use it."""

    def bind_tools(self, tools, **kwargs):
        """The scripted answers already contain the tool calls."""
        del tools, kwargs
        return self


def submit(call_id: str, **args) -> AIMessage:
    """A scripted model message that calls submit_feedback."""
    return AIMessage(content="", tool_calls=[{"name": "submit_feedback", "id": call_id,
                                              "args": args}])


def agent(*messages: AIMessage) -> LangChainCoachAgent:
    """The real agent on a scripted model."""
    chat = ScriptedChat(messages=iter(messages))
    return LangChainCoachAgent(AgentContext(InMemoryStorage()), chat_model=chat)


def test_the_agent_returns_the_feedback_it_submitted():
    """Free text -> tool call -> Feedback for the logged session."""
    feedback = agent(submit("c1", difficulty=8, all_sets_done=True, pain_location="knee"),
                     AIMessage(content="Noted.")).interpret("my knee hurt", "w1d5")
    assert (feedback.session_ref, feedback.rpe, feedback.pain_region) == ("w1d5", 8, "knee")


def test_a_wrong_argument_is_corrected_by_a_second_call():
    """The tool answers with the problem; the model calls it again with a valid value."""
    feedback = agent(submit("c1", difficulty=12, all_sets_done=True),
                     submit("c2", difficulty=7, all_sets_done=False, missed_sessions=1),
                     AIMessage(content="Noted.")).interpret("hard week", "w1d3")
    assert (feedback.rpe, feedback.all_sets_done, feedback.missed_sessions) == (7, False, 1)


def test_no_submission_raises_llm_error():
    """If the model never calls submit_feedback, the state asks the fixed questions."""
    with pytest.raises(LLMError, match="did not submit"):
        agent(AIMessage(content="How did it go?")).interpret("fine", "w1d1")


def test_a_failing_model_raises_llm_error():
    """Any model error becomes LLMError (the fallback to the fixed questions)."""
    class Broken(ScriptedChat):
        """A model that cannot answer."""

        def _generate(self, *args, **kwargs):
            """Fail like an unreachable Ollama."""
            raise ConnectionError("refused")

    broken = LangChainCoachAgent(AgentContext(InMemoryStorage()),
                                 chat_model=Broken(messages=iter([])))
    with pytest.raises(LLMError, match="ConnectionError"):
        broken.interpret("fine", "w1d1")
