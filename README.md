# Adaptive Fitness Agent

Team project for **Design Patterns UE (WS 2026/27, TU Graz)** – Example Project 3:
an agentic AI fitness coach built with LangChain. It onboards the user, generates a
training plan, asks about past workouts and adapts the plan to the answers.

> Status: implementation phase. The app runs end to end in the terminal and in a web chat UI.

## Requirements

- Python 3.11+ (we use 3.12)
- [Ollama](https://ollama.com) running locally (free, no account needed)
- About 8 GB free disk space: `qwen3` is a ~5 GB download, `qwen3:4b` ~2.5 GB

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt        # to run the app
pip install -r requirements-dev.txt    # to run tests and metrics

# 3. Download the local LLMs
ollama pull qwen3        # main model
ollama pull qwen3:4b     # only used for the model comparison metric
```

Ollama must be running before you start the app (it usually starts automatically after
installation; otherwise run `ollama serve`). Check with `ollama list`.

## Running

```bash
python -m fitness_agent.interface.main     # terminal (CLI)
python -m fitness_agent.interface.web      # web chat UI, then open http://localhost:7860
```

Your profile, plan and feedback are saved in `data/`. Without a running Ollama the app still
works: it asks fixed questions instead of reading free text and builds the plan with fixed rules.
Delete `data/` to start again as a new user.

## Using the app

1. **Onboarding.** Answer six questions in your own words (age, fitness level, goal, training days,
   equipment, injuries). A bare "yes" to the injury question gets a follow-up about the body part.
   The coach then lists your answers: type `yes` to build the plan, or the number of an answer to
   change it. Building the plan takes 1-2 minutes on a CPU.
2. **Your plan.** A 4-week plan with a lighter week 4. The web UI shows it in the panel on the
   right, one tab per week; the CLI prints it.
3. **Log a workout** (web: button, CLI: `1`). Choose the session you did, then describe how it
   went, e.g. "Squats were an 8/10 and my knee hurt a bit". The plan adapts by fixed rules (load
   up or down, a safer exercise after pain, a missed session moved), and the coach explains why.
4. **Undo last change** (web: button, shown after a change; CLI: `3`) restores the plan as it was
   before the last workout log.
5. **New plan** (web: button, CLI: `2`) starts the onboarding again; **Quit** (CLI: `q`) ends the
   session. The plan stays saved.

## Running the tests

```bash
pytest --cov          # tests, including the layer rules
lint-imports          # layer rules only (see ARCHITECTURE.md)
```

By default the tests run without Ollama. The integration tests against the local model are marked
`ollama` and run separately (Ollama must be running; they are slow on a CPU):

```bash
pytest -m ollama
```

## Baseline (`v0-baseline`)

The git tag `v0-baseline` holds a deliberately naive single-file version of the app (one God object,
if/else mode handling, copy-pasted prompts) with the same features and rules. **It is not the
submission**: it is the "before" version for our metrics and the source of our anti-pattern examples.
It is not part of the `main` branch. View it on GitHub:
[v0-baseline](https://github.com/aslikaraman/adaptive-fitness-agent/tree/v0-baseline), or check it
out locally:

```bash
git worktree add ../afa-baseline v0-baseline   # separate folder, main stays untouched
```

## Project documents

- [PATTERNS.md](PATTERNS.md) – the patterns we use, why, and the patterns we rejected
- [ARCHITECTURE.md](ARCHITECTURE.md) – the four layers, the dependency rule and how it is checked
- [FUNCTIONAL_FLOW.md](FUNCTIONAL_FLOW.md) – what the system does, step by step (onboarding → plan → feedback → adaptation)
- [AI_USAGE.md](AI_USAGE.md) – log of every AI tool use (source for the AI Usage Cards)
- [RESOURCES.md](RESOURCES.md) – external libraries, models and other resources
