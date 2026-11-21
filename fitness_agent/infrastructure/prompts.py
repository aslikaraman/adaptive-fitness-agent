"""Prompt templates for the LLM (one place for all prompt text).

Each function returns the chat messages for one LLMClient method. The shared
system text and the retry note are written once and reused.
"""

from fitness_agent.domain.models import Exercise, UserProfile
from fitness_agent.domain.plan import TrainingPlan

Messages = list[tuple[str, str]]

SYSTEM = (
    "You are the language part of a fitness coach app. You read the user's words and write "
    "short, friendly text. The app's own rules decide what is safe and what changes. "
    "Follow the requested output format exactly."
)

AGENT_SYSTEM = (
    SYSTEM + " The user tells you how a training session went. Read it, then call the tool "
    "submit_feedback exactly once with: difficulty (1-10: how hard it felt), all_sets_done "
    "(true/false), missed_sessions (planned sessions skipped, 0 if none) and pain_location "
    "(knee, shoulder, lower_back, wrist, ankle, neck or hip; leave it out if nothing hurt). "
    "If a tool answers that an argument is wrong, call it again with a corrected value. "
    "Call undo_last_change only if the user asks to take back the last change. Never invent "
    "training numbers: the app decides what changes."
)


def _messages(task: str, previous_error: str | None = None) -> Messages:
    """System text plus the task; on a retry, add why the previous answer was rejected."""
    if previous_error:
        task += f"\n\nYour previous answer was rejected: {previous_error}\nFix exactly this."
    return [("system", SYSTEM), ("human", task)]


def profile_messages(answers: str, previous_error: str | None = None) -> Messages:
    """Turn free-text onboarding answers into the UserProfile fields."""
    return _messages(
        "Extract the user's profile from their onboarding answers.\n"
        "- goal: strength, fat_loss or endurance\n"
        "- fitness_level: beginner, intermediate or advanced\n"
        "- equipment: only from bodyweight, dumbbells, barbell, kettlebell, bands, pullup_bar, "
        "machines\n"
        "- injuries: region from knee, shoulder, lower_back, wrist, ankle, neck, hip; "
        "anything else goes to injury_notes\n\n"
        f"Answers:\n{answers}",
        previous_error,
    )


def plan_messages(profile: UserProfile, constraints: str, allowed_pool: list[Exercise],
                  previous_error: str | None = None) -> Messages:
    """Choose the exercises for each session of week 1 from the allowed pool."""
    pool = "\n".join(f"- {e.id}: {e.name} ({e.movement_pattern})" for e in allowed_pool)
    return _messages(
        f"Choose the exercises for week 1 of a {profile.goal} plan for a {profile.fitness_level} "
        "user. Only choose exercise ids from the list below; the app sets sets, reps and load.\n\n"
        f"Constraints:\n{constraints}\n\nAllowed exercises:\n{pool}",
        previous_error,
    )


def summary_messages(profile: UserProfile, plan: TrainingPlan) -> Messages:
    """Explain in plain text why the plan fits the profile."""
    week = plan.weeks[0] if plan.weeks else None
    sessions = "; ".join(
        f"{s.focus}: " + ", ".join(e.exercise_id for e in s.exercises) for s in week.sessions
    ) if week else "no sessions"
    return _messages(
        "In at most three sentences, explain why this 4-week plan fits the user.\n"
        f"Profile: goal {profile.goal}, level {profile.fitness_level}, "
        f"{profile.days_per_week} days per week.\nWeek 1: {sessions}"
    )


def explanation_messages(changes: list[str]) -> Messages:
    """Explain in two sentences what changed in the plan and why, using only the given facts."""
    return _messages(
        "In at most two short sentences, tell the user what changed in their plan and why. Use "
        "only the facts below; do not add reasons, exercises or changes that are not listed.\n"
        "Facts:\n- " + "\n- ".join(changes)
    )
