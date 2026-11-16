"""The CatalogLoader interface: provides the exercise catalog (implemented by JsonCatalogLoader)."""

from abc import ABC, abstractmethod

from fitness_agent.domain.models import Exercise


class CatalogLoader(ABC):
    """Loads the exercise catalog."""

    @abstractmethod
    def load(self) -> list[Exercise]:
        """Return every exercise of the catalog."""
