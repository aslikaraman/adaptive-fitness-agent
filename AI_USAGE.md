# AI Usage Log

Every use of an AI assistant in this project is logged here. The proposal ("Use of AI tools",
§IV) promises **AI Usage Cards** in the repository, so this file has three parts:

1. **[The card template](#1-the-card-template)** — copy it for every entry you want to present.
2. **[Cards that are ready](#2-cards-ready-to-submit)** — one card per working session, already
   filled in. Only the `◻` boxes and the `«…»` placeholders need a human.
3. **[The full log](#3-the-full-log)** — the same sessions in short form, plus every session that
   has not been written up as a card yet. Nothing that happened is lost here.

**How to fill a card in 5 minutes:** open the entry, replace the `«…»` placeholders, tick the
`◻` boxes, delete the rows that do not apply, and keep the *"What we changed ourselves"* column
honest — that column is what the card is actually judged on. A card is finished when no `◻` and
no `«` is left.

---

## 1. The card template

Copy this block per entry. The seven rows match the card fields we agreed on; the last three are
what the markers ask for in the discussion (see §1.1).

```markdown
### AI Usage Card — «short title» («task number», owner: «Rahul / Aslı»)

| Field | Entry |
|---|---|
| **Date** | «YYYY-MM-DD» |
| **Tool and model** | «e.g. Claude Code (Claude Opus 5.5) / Arena.ai Agent Mode (Claude family) / ChatGPT (GPT-5)» |
| **Task we used it for** | «one sentence: which project step, and what had to be produced» |
| **Prompt (shortened)** | «the core of what we asked, in one or two sentences, quoted» |
| **Input we gave it** | «files, spec sections, slides, earlier code — this decides whether the answer could be any good» |
| **Output** | «files/artefacts it produced, with line or test counts» |
| **What we changed ourselves** | «the parts we rewrote, corrected, rejected or had to decide — be specific, this is the honest part» |
| **Used verbatim?** | ☐ Yes, unchanged ☐ Partly, after review ☐ No, only as a draft |
| **Verified by** | ☐ read line by line ☐ tests run (`pytest`) ☐ metrics run (pylint / import-linter / radon / interrogate) ☐ ran the app (CLI or web UI) ☐ discussed with the partner |
| **Effort** | generated lines: «~N» · our review/fix: «~N min» |
| **Evidence (links)** | «commit / PR / file / test name» |
```

### 1.1 Definition of done for a card

| Check | Rule |
|---|---|
| No open field | no `◻`, no `«…»` left |
| Honest share | *"What we changed ourselves"* names at least one concrete thing (not "we reviewed it") |
| Verifiable | every card points to a file, commit or test that exists |
| One card = one session | if a day has two unrelated sessions, use two cards |
| Coverage | **every** AI use in the log belongs to a card — a card may summarise several short sessions of the same task, and says so |

### 1.2 Rules of thumb (so the cards stay cheap to write)

* Write the card **the same day** (5 minutes), not at the end — the prompts get lost otherwise.
* If an artefact was produced mostly by the tool, still say what it got **wrong**; the wrong
  parts are the strongest evidence that a human checked it.
* If we threw the output away, that is a card too ("asked, not used, because …") — it shows the
  decision-making.
* Anything not from an AI tool (our own design decisions, the numbers we chose, the catalog
  review) does **not** need a card, but may be mentioned in the "changed ourselves" row.

---

## 2. Cards ready to submit

### AI Usage Card — Functional flow (Task 1, owner: Rahul)

| Field | Entry |
|---|---|
| **Date** | 2026-11-15 |
| **Tool and model** | Arena.ai Agent Mode (Claude-family model) with workspace tools |
| **Task we used it for** | Turn the proposal into a step-by-step functional flow (F1–F4) with the rules, guardrails, diagrams and test scenarios that the code would follow |
| **Prompt (shortened)** | "Write the functional flow" for onboarding → plan generation → feedback → adaptation, based on the Group 07 proposal |
| **Input we gave it** | `Design_Pattern (1).pdf` (the proposal); the four bullets of Task 1 |
| **Output** | `docs/functional_flow.md` + `.docx`: flows F1–F4, data-model sketch, RPE rule table, guardrails, Mermaid sequence + flowchart, API sketch, pattern mapping, the §12 test-scenario table (~9 000 words, 0 lines of code) |
| **What we changed ourselves** | All numbers (load steps, rep ranges, deload %, weekly caps) were **our defaults to sign off**, not sport-science advice; the decision tables were rewritten to follow the proposal's "rules decide, LLM explains"; the API sketch was dropped when the implementation became a local CLI/web app; §13 lists six open decisions we closed ourselves |
| **Used verbatim?** | ☒ No, only as a draft |
| **Verified by** | ☒ read line by line ☒ discussed with the partner ☒ re-checked against the code (the flow was updated three times while the implementation grew) |
| **Effort** | generated lines: ~0 code (~9 000 words) · our review/fix: «~N min» |
| **Evidence (links)** | `docs/functional_flow.md`, `FUNCTIONAL_FLOW.md` §6 and §12 |

### AI Usage Card — Plan generation: Strategy + Builder (owner: Rahul)

| Field | Entry |
|---|---|
| **Date** | 2026-11-15 |
| **Tool and model** | Arena.ai Agent Mode (Claude-family model) |
| **Task we used it for** | Implement plan generation: one `PlanningStrategy` per goal, a `StrategyFactory`, and a `TrainingPlanBuilder`, with the LLM choosing only the exercises inside the Strategy's constraints |
| **Prompt (shortened)** | "Implement plan generation: one Strategy per goal + StrategyFactory + TrainingPlanBuilder; the LLM only chooses exercises within the Strategy's constraints." |
| **Input we gave it** | The task text; the partner's `domain/models.py`, `domain/plan.py`, `domain/catalog.py`, `exercise_catalog.json`; `FUNCTIONAL_FLOW.md` §4–§5 |
| **Output** | `domain/strategies.py`, `domain/builder.py`, `tests/test_plan_generation.py` (114 tests) |
| **What we changed ourselves** | We fixed the first prescription drafts by hand: 1 200 s planks, bodyweight exercises inheriting a 180 s rest, `min(reps + 1, CEILING)` *lowering* reps, week 3 re-using the week-2 factor, a deload raising 1-set cardio to 2 sets, and an alphabetical (bodyweight) fallback for barbell users. We also ran a 3 024-profile matrix to check the Builder never accepts an invalid plan |
| **Used verbatim?** | ☒ Partly, after review |
| **Verified by** | ☒ read line by line ☒ tests run (`pytest`, 518 passed at that point) ☒ metrics run (coverage 100 % on both files, pylint) |
| **Effort** | generated lines: ~650 (2 source + 1 test file) · our review/fix: «~N min» |
| **Evidence (links)** | `fitness_agent/domain/strategies.py`, `fitness_agent/domain/builder.py`, `tests/test_plan_generation.py` |

### AI Usage Card — Coach agent with four tools (Task 13, owner: Rahul)

| Field | Entry |
|---|---|
| **Date** | 2026-11-15 |
| **Tool and model** | Arena.ai Agent Mode (Claude-family model) |
| **Task we used it for** | The LangChain tool-calling agent: four tools (`get_profile`, `get_current_plan`, `submit_feedback`, `undo_last_change`), `submit_feedback` hands a `Feedback` to the adaptation pipeline, and the State machine (not the agent) controls the phases |
| **Prompt (shortened)** | "Build the agent with these four tools; `submit_feedback` takes structured arguments; the plan only changes through the adaptation pipeline; raise `num_ctx`; the State machine controls the phases and falls back to fixed questions." |
| **Input we gave it** | Task 13 text; `application/coach_agent.py`, `application/llm_client.py`, `infrastructure/ollama_adapter.py`, `infrastructure/prompts.py`, `application/states.py` |
| **Output** | `infrastructure/agent.py`, `infrastructure/ollama_model.py`, `application/agent_context.py`, `tests/test_agent.py` (20 tests), `AGENT_SYSTEM` prompt, `OllamaAdapter` → `build_chat_model` |
| **What we changed ourselves** | langchain 1.5 removed `create_tool_calling_agent`/`AgentExecutor`, so we moved to `create_agent` and set the recursion limit ourselves; we found that Pydantic validates tool arguments *before* the tool body runs, so validation was tested through `_read_feedback`; we kept the agent at **one** attempt so a failure reaches the fixed questions quickly |
| **Used verbatim?** | ☒ Partly, after review |
| **Verified by** | ☒ read line by line ☒ tests run (538 passed) ☒ ran the app (agent path with a scripted model) |
| **Effort** | generated lines: ~300 (3 source + 1 test file) · our review/fix: «~N min» |
| **Evidence (links)** | `fitness_agent/infrastructure/coach_agent_langchain.py`, `fitness_agent/application/agent_context.py`, `tests/test_agent.py` |

### AI Usage Card — Adaptation pipeline with Commands and undo (Task 14, owner: Rahul)

| Field | Entry |
|---|---|
| **Date** | 2026-11-15 |
| **Tool and model** | Arena.ai Agent Mode (Claude-family model) |
| **Task we used it for** | Pipes & Filters (`SafetyFilter → ScheduleFilter → LoadFilter`, LoadFilter last), an `AdaptationContext`, one feedback cycle = one history entry, and undo = reverse-order undo of all Commands of the last cycle; Commands store a `PlanMemento` and are written once in an abstract `PlanCommand` (Template Method) |
| **Prompt (shortened)** | "Implement the adaptation pipeline per FUNCTIONAL_FLOW §6: Safety → Schedule → Load, LoadFilter last because the others can set `no_increase`; one cycle = one history entry; undo the whole cycle in reverse order; Commands with `execute()`/`undo()` and a Memento; error handling for a failing filter; the service runs the pipeline and saves through `Storage`." |
| **Input we gave it** | Task 14 text; `FUNCTIONAL_FLOW.md` §6.2–§6.5 (classification, rules, guardrails, output); `PATTERNS.md`; the partner's `domain/commands.py`, `domain/plan.py`, `domain/strategies.py`, `application/states.py`; `exercise_catalog.json` |
| **Output** | `domain/adaptation.py`, `domain/commands.py` (four concrete Commands), `application/adaptation.py` (`AdaptationService`, `HistoryEntry`), `tests/test_adaptation.py` (74), `tests/test_adaptation_service.py` (19), `tests/testing_catalog.py` |
| **What we changed ourselves** | The numbers are our spec, the tool only wrote them down (+10 %/−10 % load, ±10 s timed, ±1 rep, 70 % restart load, 2-week pattern hold, −1 set "too hard", −1 set when RPE ≥ 9). Two bugs the **coverage report** exposed were ours to find and fix: a fallback `load_factor` of 0, and a timed replacement inheriting a **kg** load from the exercise it replaced. We also de-duplicated `rounded()` into `domain/commands.py` |
| **Used verbatim?** | ☒ Partly, after review |
| **Verified by** | ☒ read line by line ☒ tests run (637 passed) ☒ metrics run (100 % on the four files, pylint 10.00/10, import-linter 2 kept) ☒ ran the app |
| **Effort** | generated lines: ~740 (3 source + 3 test files) · our review/fix: «~N min» |
| **Evidence (links)** | `fitness_agent/domain/adaptation.py`, `fitness_agent/application/adaptation.py`, `tests/test_adaptation.py` |

### AI Usage Card — Thin CLI and web chat UI (Task 15, owner: Rahul)

| Field | Entry |
|---|---|
| **Date** | 2026-11-15 (CLI) · 2026-11-21 (web UI integrated) |
| **Tool and model** | Arena.ai Agent Mode (Claude family) for the CLI and the first web view; Claude Code for the redesign of the web UI |
| **Task we used it for** | Two views on one `CoachSession`: a terminal CLI and a Gradio chat, both containing no business logic |
| **Prompt (shortened)** | "The CLI passes every input to `CoachSession`; the current state calls the application services; the interface only shows state and reads input." Then: "a web chat UI in `interface/web.py` does the same; add a loading indicator for the slow LLM steps and update the MVC row in PATTERNS.md (two views now)." |
| **Input we gave it** | Task 15 text; `ARCHITECTURE.md` layers and the "Where do I put …?" table; `application/session.py`, `application/states.py`, `tests/test_session.py` |
| **Output** | `interface/cli.py`, `interface/main.py` (composition root), `interface/web.py`, `interface/plan_view.py`, `tests/test_cli.py` (15), `tests/test_web.py` (24), plus three small edits in the application layer (`CoachSession.undo`, `UndoState`, menu option 3) |
| **What we changed ourselves** | Gradio 6 dropped `Chatbot(type="messages")` and refused to serve the button icons from outside the working directory — both found by **running** the page, both fixed by us (`allowed_paths`, per-tab `gr.State(Tab)`); the icons are our own SVGs; the welcome/goodbye wording is ours |
| **Used verbatim?** | ☒ Partly, after review |
| **Verified by** | ☒ read line by line ☒ tests run (694 passed) ☒ metrics run (web.py 100 %, pylint 10.00/10, import-linter 2 kept) ☒ ran the app (CLI with Ollama down, web UI clicked through over HTTP) |
| **Effort** | generated lines: ~365 (4 source + 2 test files) · our review/fix: «~N min» |
| **Evidence (links)** | `fitness_agent/interface/web.py`, `fitness_agent/interface/cli.py`, `tests/test_web.py` |

### AI Usage Card — Scenario tests for the adaptation rules (Task 16, owner: Rahul)

| Field | Entry |
|---|---|
| **Date** | 2026-11-15 |
| **Tool and model** | Arena.ai Agent Mode (Claude-family model) |
| **Task we used it for** | One scenario test per row of the FUNCTIONAL_FLOW §12 table (15 rows) plus the two §12 metrics (adaptation safety rate, guardrails), and unit tests for Strategies, Builder, filters and Commands including `undo()` |
| **Prompt (shortened)** | "Complete the tests: unit tests for Strategies, Builder, filters and Commands (including `undo()`); scenario tests such as 'user reports knee pain → squats are swapped and a warning is shown'." |
| **Input we gave it** | Task 16 text; `FUNCTIONAL_FLOW.md` §6.2–§6.5 and the §12 table; the existing suite; the real `exercise_catalog.json` |
| **Output** | `tests/test_scenarios.py` (33 tests), `tests/test_strategies_and_filters.py`, `tests/test_builder_and_commands.py`, and the row → test mapping in the task README |
| **What we changed ourselves** | The first draft asserted that the **logged** session changes, but §6.3 applies the rules only to the *remaining* planned occurrences — we corrected every assertion to weeks 2–4. We also had to accept the catalog's reality: every squat is knee-tagged, so knee pain on a squat takes the documented "no safe alternative → remove" branch, and only lower-back/ankle pain gives a real swap. Those three deviations are written down and need a team decision |
| **Used verbatim?** | ☒ No, only as a draft (rewritten against the real pipeline) |
| **Verified by** | ☒ read line by line ☒ tests run (509 passed, coverage 97 %) ☒ metrics run (pylint 10.00/10, radon A, interrogate 100 %) |
| **Effort** | generated lines: ~600 (3 test files) · our review/fix: «~N min» |
| **Evidence (links)** | `tests/test_scenarios.py`, `tests/test_builder_and_commands.py` |

### AI Usage Card — Running the app and fixing what it turned up (owner: Rahul)

| Field | Entry |
|---|---|
| **Date** | 2026-11-23 |
| **Tool and model** | Arena.ai Agent Mode (Claude-family model) |
| **Task we used it for** | Not a feature: build the finished repository in a clean environment, run it in eight scenarios, and report what breaks |
| **Prompt (shortened)** | "I tried to test and understand if everything applied correctly. Can you also build and run and try different scenarios?" |
| **Input we gave it** | The public repository (commit `c9813ac`) |
| **Output** | A run report (gates + 8 scenarios + 8 findings) and a small harness that drives the real services with a stand-in chat model, so the scenarios can be replayed without Ollama |
| **What we changed ourselves** | Nothing in the repository — the tool was not allowed to patch it; every finding is a **minimal reproduction** we can decide on. The four that matter: an injury that lands in `injury_notes` instead of `injuries[].region` silently disables the safety filter; a knee-tagged cardio exercise holds the whole *squat pattern* for two weeks; the quick buttons stay clickable while the coach answers, so a double click sends the menu choice twice; the web UI crashes on its button icons when started outside the repository root |
| **Used verbatim?** | ☒ Partly, after review (the reproductions were checked one by one; the "no double deload in week 4" suspicion turned out to be a non-issue) |
| **Verified by** | ☒ tests run (509 passed) ☒ metrics run (all gates) ☒ ran the app (CLI, agent path, web UI over HTTP) ☒ discussed with the partner |
| **Effort** | generated lines: ~0 in the repo (≈600 lines of harness, not committed) · our review/fix: «~N min» |
| **Evidence (links)** | the run report in the team drive; the four findings are reproducible in one command each |

---

## 3. The full log

Long entries for the sessions that produced the documents themselves; short rows for everything
else. A card above may summarise several rows of this log — the card says which.

### 3.1 Long entries

**Aslı — 2026-11-16 — Claude Code (Claude Opus 5.5).** Turned the course requirements from the
lecture slides into the project plan and reviewed it for gaps and over-engineering; completed the
functional flow (exact adaptation rules, filter order, retry rule, undo scope); defined the layered
architecture with automatic layer checks; justified the pattern set and the rejected patterns from
the slides' Context and Forces (PATTERNS.md); wrote the interface stubs. It wrote the deliberately
naive baseline (`v0-baseline`) and, step by step, the domain models with the TrainingPlan Composite
and its Memento, a first draft of the 50-entry exercise catalog (reviewed by Claude, 11 entries
corrected), the Ollama adapter with its prompts, and the State machine with the onboarding and
plan-generation services and the JSON storage, each with unit tests. It also checked all files
repeatedly against each other, the plan and the assignment slides and fixed the inconsistencies it
found. I approved every change before it was committed. → *card to write (Aslı)*

**Aslı — 2026-11-21 — Claude Code (Claude Opus 5.5).** Integrated Rahul's code for steps 12–15 and
wrote the parts it still needed, set up the web chat UI with Gradio, and tested the app against the
real qwen3 model. It added unit, scenario and integration tests and measured the coverage. Based on
my own test runs, it redesigned the web UI to be more user-friendly and improved the onboarding (a
confirmation step and a follow-up question about injuries). It also checked all documents against
the code and the lecture slides and aligned PATTERNS.md with the lecture's pattern format and names.
I approved every change before it was committed. → *card to write (Aslı)*

**Rahul — 2026-11-15 — Arena.ai Agent Mode.** Functional flow (Task 1). → card above.

**Rahul — 2026-11-15 — Arena.ai Agent Mode.** Adaptation pipeline (Task 14). → card above.

**Rahul — 2026-11-15 — Arena.ai Agent Mode.** Thin CLI (Task 15, first half). → card above.

**Rahul — 2026-11-15 — Arena.ai Agent Mode.** Scenario tests (Task 16). → card above.

**Rahul — 2026-11-15 — Arena.ai Agent Mode.** Task 15 redo: the web chat view. → card above.

**Rahul — 2026-11-15 — Arena.ai Agent Mode.** AI usage log itself: the log was restructured into
template + cards + full log, and the cards were filled from the session notes. *Generated: ~200
lines of Markdown, 0 lines of code. Our part: every „changed ourselves" row is our own account;
the placeholders (date, minutes) and the ticks must be set by the person the card belongs to.*

**Rahul — 2026-11-23 — Arena.ai Agent Mode.** Build + scenario run of the repository. → card above.

### 3.2 Short rows

| Date | Owner | Tool | What we asked / what we used the result for | Card? |
|---|---|---|---|---|
| 2026-11-16 | Aslı | Claude Code (Opus 5.5) | Project plan, architecture, pattern justification, baseline, models, catalog draft, adapter, State machine, onboarding/plan services, storage — each with tests | ◻ card to write |
| 2026-11-21 | Aslı | Claude Code (Opus 5.5) | Integration of steps 12–15, Gradio web UI, integration tests against qwen3, document alignment, PATTERNS.md format | ◻ card to write |
| 2026-11-15 | Rahul | Arena.ai Agent Mode | Functional flow (Task 1) | ☒ card above |
| 2026-11-15 | Rahul | Arena.ai Agent Mode | Plan generation: Strategy, StrategyFactory, Builder (own task) | ☒ card above |
| 2026-11-15 | Rahul | Arena.ai Agent Mode | Coach agent with four tools (Task 13) | ☒ card above |
| 2026-11-15 | Rahul | Arena.ai Agent Mode | Adaptation pipeline with Commands and undo (Task 14) | ☒ card above |
| 2026-11-15 | Rahul | Arena.ai Agent Mode | Thin CLI (Task 15) | ☒ card above |
| 2026-11-15 | Rahul | Arena.ai Agent Mode | Scenario + unit tests (Task 16) | ☒ card above |
| 2026-11-15 | Rahul | Arena.ai Agent Mode | Web chat view and the MVC row (Task 15 redo) | ☒ card above |
| 2026-11-23 | Rahul | Arena.ai Agent Mode | Build + 8 scenarios of the finished repo, 8 findings | ☒ card above |
| 2026-11-23 | Rahul | Arena.ai Agent Mode | This AI usage log (template + cards) | ☒ (mentioned in §3.1) |
| «date» | «owner» | «tool» | «what you asked and what it was used for» | ◻ |

### 3.3 How to add a new entry

1. Add a line to §3.2 (date, owner, tool, one sentence).
2. If the session produced something we hand in, copy the template from §1 into §2 and fill it.
3. If the session produced nothing we kept, say so in the same line ("asked, not used, because …").
4. Commit both changes together — the log is part of the deliverable, not an afterthought.

---

## 4. Status overview

| Owner | Sessions in the log | Cards ready | Still to do |
|---|---|---|---|
| Aslı | 2 | 0 | two cards (copy the template; the long entries already contain nearly all the text) |
| Rahul | 9 | 8 | tick the boxes, set the review minutes, add the commit links |
