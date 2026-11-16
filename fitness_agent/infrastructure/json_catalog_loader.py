"""JsonCatalogLoader: the CatalogLoader implementation for resources/exercise_catalog.json."""

import json
from pathlib import Path

from fitness_agent.application.catalog_loader import CatalogLoader
from fitness_agent.domain.models import Exercise

DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "resources" / "exercise_catalog.json"


class JsonCatalogLoader(CatalogLoader):
    """Loads and validates the exercise catalog from a JSON file."""

    def __init__(self, path: str | Path = DEFAULT_CATALOG) -> None:
        """path defaults to resources/exercise_catalog.json in the repository."""
        self._path = Path(path)

    def load(self) -> list[Exercise]:
        """Return every exercise of the catalog, validated."""
        entries = json.loads(self._path.read_text(encoding="utf-8"))
        return [Exercise.model_validate(entry) for entry in entries]
