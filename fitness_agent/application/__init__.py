"""Application layer: use cases and the control of the conversation.

Contains the application services called by the CLI (including the LLM retry
loop), the CoachSession State machine, and the interfaces (abstract base
classes) that the infrastructure layer implements: LLMClient, CoachAgent,
Storage and CatalogLoader.

Allowed imports: fitness_agent.domain and the standard library.
Must not import: fitness_agent.infrastructure, fitness_agent.interface,
LangChain or Ollama.
"""
