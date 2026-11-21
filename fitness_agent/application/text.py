"""Plain-text descriptions the states show to the user."""

from fitness_agent.domain.plan import PlannedExercise, Session, TrainingPlan

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def readable(name: str) -> str:
    """"goblet_squat" -> "Goblet squat", "push" -> "Push"."""
    return name.replace("_", " ").capitalize()


def describe_session(week: int, session: Session) -> str:
    """One training day, e.g. "Week 1 · Mon · Push"."""
    return f"Week {week} · {WEEKDAYS[session.day_of_week - 1]} · {readable(session.focus)}"


def describe_exercise(exercise: PlannedExercise) -> str:
    """One line for one exercise, e.g. "goblet_squat: 3 x 10, 20.0 kg, rest 60 s"."""
    if exercise.load_type == "kg":
        load = f"{exercise.load} kg"
    elif exercise.load_type == "time":
        load = f"{round(exercise.load)} s"
    else:
        load = "bodyweight"
    return (f"{exercise.exercise_id}: {exercise.sets} x {exercise.reps}, {load}, "
            f"rest {exercise.rest_s} s")


def describe_plan(plan: TrainingPlan) -> str:
    """The whole plan, week by week, with the coach summary on top."""
    lines = [plan.coach_summary] if plan.coach_summary else []
    for week in plan.weeks:
        lines.append(f"\nWeek {week.number}")
        for session in week.sessions:
            lines.append(f"  Day {session.day_of_week} ({session.focus}) [{session.status}]")
            lines.extend(f"    {describe_exercise(exercise)}" for exercise in session.exercises)
    return "\n".join(lines)
