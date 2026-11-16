# Adaptive Fitness Agent

Team project for **Design Patterns UE (WS 2026/27, TU Graz)** – Example Project 3:
an agentic AI fitness coach built with LangChain. It onboards the user, generates a
training plan, asks about past workouts and adapts the plan to the answers.

> Status: setup phase. Usage instructions will be added as the application is built.

## Requirements

- Python 3.11+ (we use 3.12)
- [Ollama](https://ollama.com) running locally (free, no account needed)

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

## Running

```bash
python -m fitness_agent.interface.main
```

_The application is still being built._

## Running the tests

```bash
pytest --cov          # tests, including the layer rules
lint-imports          # layer rules only (see ARCHITECTURE.md)
```

## Project documents

- [ARCHITECTURE.md](ARCHITECTURE.md) – the four layers, the dependency rule and how it is checked
- [FUNCTIONAL_FLOW.md](FUNCTIONAL_FLOW.md) – what the system does, step by step (onboarding → plan → feedback → adaptation)
- [AI_USAGE.md](AI_USAGE.md) – log of every AI tool use (source for the AI Usage Cards)
- [RESOURCES.md](RESOURCES.md) – external libraries, models and other resources
