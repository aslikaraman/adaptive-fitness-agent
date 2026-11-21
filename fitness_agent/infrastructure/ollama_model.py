"""The one place that builds the ChatOllama model, so every LLM user shares the same settings."""

from langchain_ollama import ChatOllama

DEFAULT_MODEL = "qwen3"
NUM_CTX = 8192  # a larger context window helps tool calling (the agent sees tools and plan)


def build_chat_model(model: str = DEFAULT_MODEL, num_predict: int = 1000,
                     num_ctx: int | None = None) -> ChatOllama:
    """ChatOllama with temperature 0, thinking off and a capped output length."""
    options = {"num_ctx": num_ctx} if num_ctx else {}
    return ChatOllama(model=model, temperature=0, reasoning=False, num_predict=num_predict,
                      **options)
