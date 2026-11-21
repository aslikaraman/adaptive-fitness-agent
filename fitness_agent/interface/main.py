"""Composition root: the only place that creates the concrete objects.

It builds the infrastructure implementations (OllamaAdapter, the LangChain agent, JSON
storage, the catalog loader), passes them into the application layer through its interfaces,
and starts the CLI. No other module chooses a concrete implementation.

Run the CLI with:     python -m fitness_agent.interface.main
Run the web UI with:  python -m fitness_agent.interface.web
"""

from fitness_agent.application.adaptation import AdaptationService
from fitness_agent.application.agent_context import AgentContext
from fitness_agent.application.onboarding import OnboardingService
from fitness_agent.application.planning import PlanService
from fitness_agent.application.session import CoachSession
from fitness_agent.domain.strategies import StrategyFactory
from fitness_agent.infrastructure.coach_agent_langchain import LangChainCoachAgent
from fitness_agent.infrastructure.json_catalog_loader import JsonCatalogLoader
from fitness_agent.infrastructure.json_storage import JsonStorage
from fitness_agent.infrastructure.ollama_adapter import OllamaAdapter
from fitness_agent.interface.cli import Cli


def build_session(data_dir: str = "data") -> CoachSession:
    """Wire the layers together and return a new, not yet started CoachSession."""
    storage = JsonStorage(data_dir)
    catalog = JsonCatalogLoader()
    llm = OllamaAdapter()
    strategies = StrategyFactory()
    adaptation = AdaptationService(storage, catalog, llm=llm, strategies=strategies)
    # the agent only reads the Feedback; the feedback state saves it and adapts the plan
    agent = LangChainCoachAgent(AgentContext(storage, undo=adaptation.undo_last_change))
    return CoachSession(OnboardingService(llm, storage),
                        PlanService(llm, catalog, storage, strategies),
                        storage, adaptation, agent)


def main() -> None:
    """Start the CLI."""
    Cli(build_session()).run()


if __name__ == "__main__":
    main()
