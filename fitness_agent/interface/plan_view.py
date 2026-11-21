"""The side panel of the web UI: the current plan as HTML cards (presentation only).

It reads the TrainingPlan and the UserProfile that the session holds and turns them into
markup; it never changes them. The coach's rules stay in the application and domain layers.
"""

from html import escape

from fitness_agent.domain.models import UserProfile
from fitness_agent.domain.plan import PlannedExercise, Session, TrainingPlan, Week

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
STATUS_LABELS = {"planned": "Planned", "done": "Done", "missed": "Missed", "dropped": "Dropped"}
GOAL_LABELS = {"strength": "💪 Strength", "fat_loss": "🔥 Fat loss", "endurance": "🏃 Endurance"}

HOW_IT_WORKS = """
<div class="fa-panel fa-empty">
  <h3>How it works</h3>
  <ol class="fa-steps">
    <li><b>Tell the coach about you</b><span>Age, level, goal, training days, equipment and
      injuries, in your own words.</span></li>
    <li><b>Get a 4-week plan</b><span>Built from safe exercises for your equipment, with a
      lighter week 4.</span></li>
    <li><b>Log each workout</b><span>Say how it felt, e.g. “Squats were an 8/10 and my knee
      hurt a bit.”</span></li>
    <li><b>The plan adapts</b><span>Loads, exercises and days change by fixed rules, and every
      change can be undone.</span></li>
  </ol>
</div>
"""


def exercise_name(exercise_id: str) -> str:
    """"goblet_squat" -> "Goblet squat"."""
    return exercise_id.replace("_", " ").capitalize()


def dose(exercise: PlannedExercise) -> str:
    """Sets, reps or time, and load, e.g. "3 × 8 · 12.5 kg" or "2 × 30 s"."""
    if exercise.load_type == "time":
        return f"{exercise.sets} × {round(exercise.load)} s"
    load = f"{exercise.load:g} kg" if exercise.load_type == "kg" else "bodyweight"
    return f"{exercise.sets} × {exercise.reps} · {load}"


def current_week(plan: TrainingPlan) -> int:
    """The first week that still has a planned session (the last week when all are over)."""
    for week in plan.weeks:
        if any(s.status == "planned" for s in week.sessions):
            return week.number
    return plan.weeks[-1].number if plan.weeks else 1


def _session_card(session: Session) -> str:
    """One training day: weekday, focus, status and its exercises."""
    rows = "".join(
        f'<li><span class="fa-ex">{escape(exercise_name(e.exercise_id))}</span>'
        f'<span class="fa-dose">{escape(dose(e))}</span>'
        f'<span class="fa-rest">rest {e.rest_s} s</span></li>'
        for e in session.exercises)
    return (f'<div class="fa-session fa-{session.status}">'
            f'<div class="fa-session-head"><span class="fa-day">'
            f'{WEEKDAYS[session.day_of_week - 1]}</span>'
            f'<span class="fa-focus">{escape(exercise_name(session.focus))}</span>'
            f'<span class="fa-badge">{STATUS_LABELS.get(session.status, session.status)}</span>'
            f'</div><ul>{rows}</ul></div>')


def _week(week: Week, is_current: bool) -> str:
    """One collapsible week; the current week is open."""
    done = sum(s.status == "done" for s in week.sessions)
    label = " · this week" if is_current else ""
    cards = "".join(_session_card(s) for s in week.sessions)
    return (f'<details class="fa-week"{" open" if is_current else ""}><summary>'
            f'<b>Week {week.number}</b>{label}<span class="fa-count">{done}/{len(week.sessions)}'
            f' done</span></summary>{cards}</details>')


def _profile_chips(profile: UserProfile | None) -> str:
    """Goal, level and training days as small chips."""
    if profile is None:
        return ""
    chips = [GOAL_LABELS.get(profile.goal, profile.goal),
             f"🎯 {profile.fitness_level.capitalize()}",
             f"📅 {profile.days_per_week} days / week"]
    return '<div class="fa-chips">' + "".join(
        f'<span class="fa-chip">{escape(c)}</span>' for c in chips) + "</div>"


def render_plan(plan: TrainingPlan | None, profile: UserProfile | None) -> str:
    """The whole side panel: progress, profile, coach summary and the weeks."""
    if plan is None or not plan.weeks:
        return HOW_IT_WORKS
    sessions = [s for w in plan.weeks for s in w.sessions]
    done = sum(s.status == "done" for s in sessions)
    percent = round(100 * done / len(sessions)) if sessions else 0
    summary = (f'<p class="fa-summary">{escape(plan.coach_summary)}</p>'
               if plan.coach_summary else "")
    now = current_week(plan)
    weeks = "".join(_week(w, w.number == now) for w in plan.weeks)
    return (f'<div class="fa-panel"><h3>Your training plan</h3>{_profile_chips(profile)}'
            f'<div class="fa-progress"><div class="fa-progress-text"><span>{done} of '
            f'{len(sessions)} sessions done</span><b>{percent} %</b></div>'
            f'<div class="fa-bar"><div style="width:{percent}%"></div></div></div>'
            f'{summary}{weeks}</div>')
