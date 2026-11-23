# Build & scenario run of the GitHub repo — findings

**Repo:** `github.com/aslikaraman/adaptive-fitness-agent` @ `c9813ac` ("Align the patterns with the lecture and document how to use the app")
**When:** 2026-11-23 · **Where:** clean sandbox, Python 3.13.18, Linux, 2 cores / 1 GB RAM

---

## 1. Build — clean, nothing to fix

```
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
```
All pinned versions resolve and install without a conflict: gradio 6.32.0, langchain 1.5.0,
langchain-ollama 1.1.0, pydantic 2.14.3, pytest 9.2.0, pylint 4.1.4, import-linter 2.16, radon,
interrogate. `requirements.txt` and `requirements-dev.txt` are consistent (`-r` include works).

| Gate | Result |
|---|---|
| `pytest -q` | **509 passed, 4 deselected** (the `ollama` marker), 3.7 s |
| `pytest -q --cov` | **TOTAL 97 %** |
| `pylint fitness_agent tests` | **10.00 / 10** |
| `lint-imports` | **2 contracts kept, 0 broken** |
| `radon cc -a` | 301 blocks, average **A (2.70)** |
| `interrogate` | **100 %** |
| `pytest -m ollama` | 3 failed, 1 passed — **expected**: no Ollama (`Connection refused`) |

Files that pull the coverage below 100 % (worth a look, none of them broken):

```
application/adaptation.py        89 %  lines 55, 79, 96-99, 107-108
domain/adaptation.py             92 %  (22 lines)
domain/builder.py                90 %  (6 lines)
interface/cli.py                 93 %  lines 30, 35
interface/main.py                91 %  lines 40, 44
```

So: **the repo builds and the suite is green.** Everything below comes from *running* it, not
from reading it.

### What I could not run

Ollama itself: the sandbox has **1 GB RAM / 2 cores**, and a quantised `qwen3` needs ~5 GB, so
the three `-m ollama` tests cannot run here. Everything else is the real code — the real
`OllamaAdapter`, prompts, Pydantic validation, State machine, adaptation pipeline, Commands,
`JsonStorage`, CLI and the Gradio view. Only the **chat model inside the adapter** is replaced
(a stand-in object that answers each of the five LLM calls); one scenario also runs the real
LangChain tool-calling loop with a scripted model, so the four tools and `submit_feedback`
were exercised for real.

**One side effect worth knowing:** with Ollama down the app is not unusable — it falls back to
the fixed onboarding questions, then to the rule-based plan and template texts
(scenario 6 below). That path is what I explored most.

---

## 2. Scenarios that ran correctly (reproduce with `scenarios.py`)

| # | Scenario | Result |
|---|---|---|
| 1 | strength / 3 days, onboarding → confirm → plan → RPE 6 feedback → undo → quit | plan built from the LLM draft (1 `PlanDraft` call), RPE 6 = ON_TARGET (only the session is marked `done`), undo restores the exact pre-cycle plan |
| 2 | onboarding with "my knee hurts when I squat" (mapped to `injuries=[knee]`) | plan contains **no** squat at all (all 9 squats in the catalog are knee-tagged) |
| 3 | knee pain reported after the leg day | see finding **B2** (removal, with the "see a professional" warning — documented behaviour, debatable UX) |
| 4 | **free text** "my knee really hurt on the last set, it was brutal" → real LangChain agent | agent calls `submit_feedback(difficulty=9, pain_location="knee")`, the pipeline then adapts (finding B2 again) |
| 5 | fat loss 3 d, endurance 2 d, strength 4 d | different split, rep ranges (12 vs 5/6), rest (45 s vs 180 s), timed cardio; week 4 is a lighter week in all three |
| 6 | **every LLM call fails** | fixed onboarding questions → rule-based plan (`llm_generated=False`) → templated summary; the app never depends on the model |
| 7 | two feedbacks, two undos, then a **new process** on the same `data/` | JSON storage round-trips; the restart shows the saved, adapted plan and the `[done]` session |
| 8 | the Gradio view over real HTTP (`gradio_client`) | page opens, quick buttons (`Log a workout`, `New plan`, `Undo`, `Quit`) appear only at the menu, the **Undo button appears only after a change**, the plan panel refreshes (week 2 showed `3 × 6 · 42 kg`), undo brings the old loads back |

The rules themselves behaved as documented: +5 % for a squat / +2.5 % otherwise, one increase
per exercise per week, ≥ 2 sets, ≤ 1 rest day kept when a session is moved, week 4 = deload,
pain never raises a load, undo is byte-identical to the previous plan.

---

## 3. Problems found (reproduce with `bug_reports.py`)

Ordered by how much I would care before the demo.

### B1 — *medium* A tiny injury detail can delete a main lift
`SafetyFilter` holds a **pattern** (`movement_pattern`) for two weeks when it removes an
exercise; the hold is keyed by pattern only, not by region.

```
day 1: back_squat, barbell_bench_press, barbell_row, burpee
feedback: RPE 7, knee pain
→ "Barbell back squat is removed … no exercise in your pool trains the same movement safely"
→ held_patterns = {'squat': 2}
```
`burpee` (cardio, knee-tagged) is the *other* offender, and because **every** squat is
knee-tagged the whole squat pattern is held for two weeks. Result: the leg day loses its main
lift *and* the squat pattern is blocked even for a compliant user. Two independent causes:
1. the catalog has **no knee-friendly squat** (all 9 are tagged `knee`) — a catalog decision
   for Aslı, same finding as in the task-16 review;
2. the hold is per pattern, so one cardio exercise's removal blocks the squat pattern too.

*Suggestion:* hold only the pattern of the removed exercise *for that region*, and/or add one
knee-safe squat (short range, band-assisted, high box) to the catalog.

### B2 — *medium* Pain on a squat ends with "the exercise is removed", never with a swap
Consequence of B1's cause 1: for a knee complaint the "no safe alternative" branch fires on
every squat, so the user reads *"Bodyweight squat is removed …"* instead of *"replaced by …"*.
The warning and the load rule are fine; the message is the problem. Section §6.3 of
FUNCTIONAL_FLOW.md is satisfied, but the §12 table row "knee pain → squats are swapped" cannot
be demonstrated with the current catalog.

### B3 — *medium* An injury that lands in `injury_notes` disables the safety filter
`allowed_pool()` filters on `profile.injuries[].region`; `injury_notes` only adds a sentence to
the coach summary.

| profile | squats in the allowed pool |
|---|---|
| `injuries=[{region: "knee"}]` | **none** (correct) |
| `injuries=[], injury_notes=["my knee hurts when I squat"]` | `bw_squat, box_step_up, wall_sit, goblet_squat, split_squat, back_squat` |

The prompt asks the model for `injuries: region from knee, shoulder, …` and puts "anything
else" into `injury_notes`, so this happens whenever qwen3 writes *"knee hurts when squatting"*
into the notes. The fixed-question path is safe (the parser gives a region), so the risk is
**only on the LLM path** — i.e. exactly the normal path on a laptop with Ollama running.

*Suggestion:* after `extract_profile`, scan `injury_notes` for the seven region words and move
them into `injuries` (a 5-line normaliser in `OnboardingService`, or a Pydantic validator on
`UserProfile`). Cheap and removes a whole class of silent failures.

### B4 — *low* One click too many can drop a session from the plan
Clicking a quick button while the coach is still answering sends the menu choice twice:
```
user: 1   assistant: (thinking)      ← first click
user: 1   assistant: Which session did you do?
```
The input box is locked during the answer but the **buttons are not**; both queued clicks are
delivered. So far the second `1` lands on the session question — harmless here, but with
`2` (new plan) or `3` (undo) the second click hits the *next* state and does something else.
*Suggestion:* hide/disable `quick` in `posted()` (it is already being returned as an output —
one `visible=False` more) or ignore a message while `Tab.pending` is set.

### B5 — *low* The quick buttons crash if the app is started from another directory
Gradio refuses to serve the button icons/avatars (`.svg` next to `web.py`) unless they are
inside the working directory or in `allowed_paths`. Started from the repo root it is fine
(that is `python -m fitness_agent.interface.web`), started from anywhere else:
```
gradio.exceptions.InvalidPathError: Cannot move …/interface/assets/undo.svg to the gradio cache …
```
I hit this from my harness and worked around it with `allowed_paths`. One-line fix in
`web.main()`: `allowed_paths=[str(ASSETS)]`.

### B6 — *low* A timed exercise prints "1 × 1"
Timed exercises keep `reps = 1` (`default_rep_range = (1, 1)`, `load_type = time`), so
`describe_exercise()` and the plan panel print e.g. `farmer_carry: 3 x 1, 45 s` / `Burpee |
1 × 505 s`. In the CLI table "3 x 1, 45 s" reads like a typo. *Suggestion:* print `3 × 45 s`
when `load_type == "time"` (2 lines in `application/text.py` and `interface/plan_view.py`).

### B7 — *low* The `push / pull / legs` label is gone
Every session's focus comes out as `auto` in all my runs (the prompt does not ask the model for
a focus, and the fallback has none), so the CLI shows `Day 1 (auto)` and the plan panel has no
title for the day. Earlier runs showed `Day 1 (push)`. Either ask for `focus` in
`plan_messages` or derive it from the exercises — otherwise the demo loses a nice touch.

### B8 — *very low* The "no increase in week 4" guardrail is silent
A too-easy feedback reported on a week-4 session correctly raises nothing (week 4 is the deload
week), and the message only says "too easy: … " for the exercises that did change — for the
week-4 occurrences the plan looks untouched with no explanation. Cosmetic.

### Non-issues I checked and that are fine
* Week 4 double deload (x0.9 twice) — good news: the guardrail **already** stops it; an RPE-10
  feedback on a week-4 session leaves week 4 unchanged.
* Restart on the same `data/` directory keeps profile, plan, statuses and `held_patterns`.
* The retry budget is shared: a draft the Builder keeps rejecting costs exactly 3 `PlanDraft`
  calls and then falls back (`llm_generated=False`).
* `pytest -m ollama` failing without Ollama is by design; the tests are skipped by the default
  `addopts`.

---

## 4. How to re-run everything

```bash
# in the repo
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q                      # 509 passed

# the scenario run (fake chat model inside the real adapter)
<repo>/.venv/bin/python /home/user/harness/scenarios.py 1 2 3 4 5 6 7 8
# the problems above, one minimal reproduction each
<repo>/.venv/bin/python /home/user/harness/bug_reports.py

# the real web UI without Ollama (click through it)
cd <repo> && .venv/bin/python /home/user/harness/serve_demo.py 7860
```

`harness/harness.py` is the only new code: a stand-in chat model for `OllamaAdapter` plus a
`make_session()` that wires the real services. Nothing in the repo was modified.

---

## 5. Suggested order of work

1. **B3** (normalise `injury_notes` → `injuries`) — the only finding that can produce an
   *unsafe plan* on the normal LLM path, and it is a few lines.
2. **B5** (`allowed_paths`) and **B4** (lock the buttons) — two tiny UI fixes that remove
   crashes / double actions in the demo.
3. **B1 / B2** — needs a decision with Aslı: add one knee-safe squat to the catalog and hold
   the pattern per region, or keep the removal message and say so in the report.
4. **B6 / B7** — presentation only, but they are what the markers see on the screen.
