"""Infrastructure layer: everything that talks to the outside world.

Contains the implementations of the application interfaces: OllamaAdapter
(LLMClient), the LangChain agent (CoachAgent), JsonStorage (Storage),
JsonCatalogLoader (CatalogLoader), and the prompt templates.

Allowed imports: fitness_agent.application, fitness_agent.domain, LangChain,
Ollama and the standard library.
Must not import: fitness_agent.interface.
"""
