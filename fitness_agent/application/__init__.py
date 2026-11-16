"""Application layer: use cases and the control of the conversation.

Contains the CoachSession State machine (the only entry point for the CLI),
the application services its states call (including the LLM retry loop),
and the interfaces (abstract base classes) that the infrastructure layer
implements: LLMClient, CoachAgent, Storage and CatalogLoader.

Allowed imports: fitness_agent.domain and the standard library.
Must not import: fitness_agent.infrastructure, fitness_agent.interface,
LangChain or Ollama.
"""
