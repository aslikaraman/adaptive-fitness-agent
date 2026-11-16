# Adaptive Fitness Agent – naive baseline (`v0-baseline`)

**This is not the submission.** It is the deliberate "before" version of our project: a single file
(`coach.py`) with the same features and rules as the final version, written without any structure.
We use it as the baseline for our metrics (baseline vs. final) and as the source of our anti-pattern
examples. The submission is on the `main` branch.

## Anti-patterns it contains on purpose

| Anti-pattern | Where |
|---|---|
| **God object** | `FitnessCoach` holds the profile, plan, feedback, history, LLM calls, rules, storage and CLI |
| **Mode handling with if/else** | `run()` switches on `self.mode` instead of using states |
| **Cut-and-Paste Programming** | the prompt header, the JSON extraction and the 3-attempt retry loop are copied into every LLM call; the catalog lookup and the "apply to all remaining sessions" loop are copied into every rule |
| **Scattered conditionals** | the load-type rules (`if lt == "kg" ... elif lt == "time" ...`) are repeated in every adaptation rule; the goal rules are one big `if p["goal"] == ...` block inside `run()` |
| **Tight coupling** | LangChain/Ollama, JSON files and `input()`/`print()` are used directly inside the business rules, so no rule can be unit-tested on its own: it only runs inside the interactive loop |

## Running it

Needs Python 3.11+ and a running Ollama with the `qwen3` model.

```bash
pip install -r requirements.txt
python coach.py
```

The state is saved in `data/baseline_state.json`.
