"""JsonStorage: the Storage implementation with one JSON file per kind of data."""

import json
from pathlib import Path

from fitness_agent.application.storage import Storage
from fitness_agent.domain.models import Feedback, UserProfile
from fitness_agent.domain.plan import TrainingPlan


class JsonStorage(Storage):
    """Saves profile.json, plan.json and feedback.json in one directory (data/ by default)."""

    def __init__(self, directory: str | Path = "data") -> None:
        """The directory is created on the first save."""
        self._directory = Path(directory)

    def _path(self, name: str) -> Path:
        """The file for one kind of data."""
        return self._directory / f"{name}.json"

    def _write(self, name: str, data) -> None:
        """Write data as JSON, creating the directory if needed."""
        self._directory.mkdir(parents=True, exist_ok=True)
        self._path(name).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _read(self, name: str):
        """Read the JSON data, or None if the file does not exist."""
        path = self._path(name)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_profile(self, profile: UserProfile) -> None:
        """Save the profile, replacing any earlier one."""
        self._write("profile", profile.model_dump())

    def load_profile(self) -> UserProfile | None:
        """Return the saved profile, or None if there is none."""
        data = self._read("profile")
        return None if data is None else UserProfile.model_validate(data)

    def save_plan(self, plan: TrainingPlan) -> None:
        """Save the plan, replacing any earlier one."""
        self._write("plan", plan.model_dump())

    def load_plan(self) -> TrainingPlan | None:
        """Return the saved plan, or None if there is none."""
        data = self._read("plan")
        return None if data is None else TrainingPlan.model_validate(data)

    def save_feedback(self, feedback: Feedback) -> None:
        """Append one feedback to the saved feedback."""
        feedbacks = self._read("feedback") or []
        feedbacks.append(feedback.model_dump())
        self._write("feedback", feedbacks)

    def load_feedbacks(self) -> list[Feedback]:
        """Return all saved feedback, oldest first."""
        return [Feedback.model_validate(item) for item in self._read("feedback") or []]
