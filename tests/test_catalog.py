"""Tests for resources/exercise_catalog.json (FUNCTIONAL_FLOW.md §2)."""

import json
from itertools import product
from pathlib import Path
from typing import get_args

import pytest

from fitness_agent.domain.models import (KNOWN_EQUIPMENT, KNOWN_REGIONS, LEVELS, Exercise,
                                         MovementPattern)

CATALOG_FILE = Path(__file__).resolve().parent.parent / "resources" / "exercise_catalog.json"


@pytest.fixture(scope="module", name="catalog")
def fixture_catalog() -> list[Exercise]:
    """Every entry of the catalog, validated as an Exercise."""
    with CATALOG_FILE.open(encoding="utf-8") as file:
        return [Exercise.model_validate(entry) for entry in json.load(file)]


def allowed_pool(catalog, equipment, injuries, level, minor=False):
    """The exercises a profile may do: equipment available, not contraindicated, level not above."""
    return [exercise for exercise in catalog
            if set(exercise.required_equipment) <= set(equipment) | {"bodyweight"}
            and not set(exercise.contraindicated_regions) & set(injuries)
            and LEVELS.index(exercise.level) <= LEVELS.index(level)
            and not (minor and exercise.level == "advanced")]


def test_catalog_size_and_unique_ids(catalog):
    """About 40-60 entries, no duplicate ids."""
    assert 40 <= len(catalog) <= 60
    assert len({exercise.id for exercise in catalog}) == len(catalog)


def test_catalog_covers_every_pattern_equipment_and_level(catalog):
    """Every movement pattern, equipment option and level appears at least once."""
    assert {e.movement_pattern for e in catalog} == set(get_args(MovementPattern))
    assert {item for e in catalog for item in e.required_equipment} == set(KNOWN_EQUIPMENT)
    assert {e.level for e in catalog} == set(LEVELS)


def test_timed_exercises_use_one_rep(catalog):
    """For timed exercises the duration is the load, so the rep range is 1-1."""
    assert all(e.default_rep_range == (1, 1) for e in catalog if e.load_type == "time")


@pytest.mark.parametrize("level, item, injury, minor", list(product(
    LEVELS, KNOWN_EQUIPMENT, (None,) + KNOWN_REGIONS, (False, True))))
def test_every_profile_has_a_non_empty_pool(catalog, level, item, injury, minor):
    """Every level x equipment option x (no injury or any one injury) x minor gets exercises."""
    injuries = [injury] if injury else []
    assert allowed_pool(catalog, [item], injuries, level, minor)


def test_bodyweight_beginner_with_every_injury_still_has_exercises(catalog):
    """The worst case: no equipment, beginner, all seven regions injured."""
    assert allowed_pool(catalog, ["bodyweight"], list(KNOWN_REGIONS), "beginner")
