"""The hard safety filter on the exercise catalog (FUNCTIONAL_FLOW.md §4.3)."""

from fitness_agent.domain.models import LEVELS, Exercise, UserProfile


def allowed_pool(catalog: list[Exercise], profile: UserProfile) -> list[Exercise]:
    """The exercises this profile may do.

    An exercise is allowed if the user has its equipment, it is not contraindicated for a
    reported injury, its level is not above the user's level, and it is not advanced for a minor.
    """
    equipment = set(profile.equipment)
    injuries = {injury.region for injury in profile.injuries}
    max_level = LEVELS.index(profile.fitness_level)
    return [
        exercise for exercise in catalog
        if set(exercise.required_equipment) <= equipment
        and not set(exercise.contraindicated_regions) & injuries
        and LEVELS.index(exercise.level) <= max_level
        and not (profile.minor and exercise.level == "advanced")
    ]
