# Design Patterns

The patterns we use, why we use them, and the patterns we rejected on purpose.

## Governing rule

**The LLM handles language, our code handles logic.** The LLM reads the user's words, chooses the
exercises for week 1 and explains changes; the training numbers come from our code. Every decision (is the plan safe, does it change, by how much) is
made by deterministic code, so it can be tested without a model.

## Patterns we use

### Layers (Architectural)

- **Problem:** the app mixes four responsibilities that change for different reasons: the CLI,
  the conversation flow, the training rules, and external details (Ollama, LangChain, JSON files).
- **Why:** changes should be limited to one component, parts should be exchangeable (e.g. another LLM
  provider), and interfaces should be stable.
- **Where:** `fitness_agent/domain`, `application`, `infrastructure`, `interface`; see
  [ARCHITECTURE.md](ARCHITECTURE.md). `interface/main.py` composes the layers at runtime; interfaces are
  abstract base classes in `application/`.
- **Trade-off:** swapping the LLM or the storage touches one layer, but a new field (e.g. in `Feedback`)
  can cascade through domain, agent tool and CLI.

### State (Behavioral)

- **Problem:** the coach behaves differently in onboarding, plan review, feedback and adaptation.
  Without State this becomes `if mode == ...` blocks spread over the code.
- **Why:** behaviour should change with the internal state, transitions should not depend on complex
  conditional statements, and states should not be mixed.
- **Where:** `CoachSession` (Context) with `OnboardingState`, `PlanReviewState`, `FeedbackState`,
  `AdaptationState`. Each state's `handle()` returns the next state; `CoachSession` only stores and
  calls the current one.
- **Trade-off:** a new phase is a new class, but the flow needs four extra classes.

### Adapter (Wrapping)

- **Problem:** LangChain/Ollama calls, their output types and their exceptions would otherwise leak
  into the application code and make it untestable without a running model.
- **Why:** it isolates an external interface behind our own.
- **Where:** `LLMClient` (target, `application/`) ← `OllamaAdapter` (adapter, `infrastructure/`) →
  `ChatOllama` from langchain-ollama (adaptee). `FakeLLMClient` implements the same interface for tests.
- **Trade-off:** changing provider or model is one new class and tests run without Ollama, at the cost
  of one interface plus one translation layer.

### Strategy, chosen by a Simple Factory (Behavioral)

- **Problem:** strength, fat-loss and endurance plans differ in split, rep ranges, set limits, rest
  times and progression. A goal-based `if/else` would appear in three places: the plan skeleton, the
  Builder's limits and the adaptation guardrails.
- **Why:** we need different variants of one algorithm, and the same variation should be handled in
  one place.
- **Where:** `PlanningStrategy` (interface) with `StrengthStrategy`, `FatLossStrategy`,
  `EnduranceStrategy`. `StrategyFactory.create(profile)` picks the strategy at runtime with a lookup from
  `goal` to strategy class (a Simple Factory: one concrete class, no Creator hierarchy).
- **Trade-off:** a new goal is one new class plus one line in the factory, at the cost of three classes
  and a factory instead of one function.

### Composite (Behavioral)

- **Problem:** a plan is a hierarchy: plan → week → session → exercise. Volume, duration and
  intensity scaling are needed at every level.
- **Why:** all granularities should be treated uniformly, and one call should reach all objects.
- **Where:** `TrainingPlan`, `Week`, `Session` (composites) and `PlannedExercise` (leaf), all with
  `total_volume()`, `duration()`, `scale_intensity(factor)`.
- **Trade-off:** the same call works on a whole plan or one session, but a call on the plan is hidden
  work on every exercise.

### Builder (Creational)

- **Problem:** a `TrainingPlan` is a complex object assembled from two different sources, the LLM
  draft and the deterministic fallback, and it must be valid before anyone uses it.
- **Why:** creating a complex object should be independent of how its parts are assembled.
- **Where:** `TrainingPlanBuilder` with `start_week()`, `add_session()`, `add_exercise()`, `build()`.
  The plan service (LLM draft) and the Strategy (fallback, weeks 2–4) both direct it. `build()` is the
  only way to get a `TrainingPlan` and runs the validation gate (schema, allowed pool, volume,
  structure), so every plan is correctly configured.
- **Trade-off:** both creation paths share one validation, but construction is no longer a simple
  constructor call.

### Pipes & Filters (Architectural)

- **Problem:** each feedback goes through the same sequence of independent rules: safety first,
  then schedule, then load.
- **Why:** processing steps should be exchangeable and reorderable, and small steps are easier to
  reuse and test than one large one.
- **Where:** `SafetyFilter → ScheduleFilter → LoadFilter` with a common `process(context)` interface and
  `AdaptationContext` as the data format along the pipe. If a filter fails, no Command is executed and
  the plan stays unchanged.
- **Trade-off:** a new rule is a new filter, testable alone, but shared information has to travel in
  the context object and the order of the filters matters.

### Command + Memento (Behavioral + Creational)

- **Problem:** the user must be able to undo an adaptation, and the plan must only change in
  controlled, logged steps.
- **Why:** requests should be undoable, and the plan's state should be stored and restored without
  exposing its internals.
- **Where:** filters create `SwapExerciseCommand`, `AdjustVolumeCommand`, `RescheduleCommand` (with all
  parameters as members); `execute()` stores a `PlanMemento` of the `TrainingPlan` (originator), `undo()`
  restores it, so each Command is the caretaker of its Memento; the history keeps the executed Commands,
  one entry per feedback cycle.
- **Trade-off:** undo and the change history come for free and filters only decide while Commands
  change, at the cost of more objects and one plan snapshot per change.

### Template Method (Behavioral)

- **Problem:** all three Commands do the same thing around their change: store a Memento before
  changing the plan and restore it on undo. Written in each Command, this code would be copied three
  times (Cut-and-Paste Programming).
- **Why:** the parent class fixes the order of steps, and the subclasses implement one step.
- **Where:** abstract `PlanCommand.execute(plan)` stores the `PlanMemento`, then calls `_apply(plan)`,
  which each concrete Command implements; `undo()` is written once in `PlanCommand`. The question
  states use the same idea: `AskingState` fixes ask → validate → re-ask, and `OnboardingState` and
  `FeedbackState` only add their questions and their next state.
- **Trade-off:** a new Command only implements `_apply()` and cannot forget the Memento, but the
  Commands share a base class.

### Retry with Fallback (Resilience)

- **Problem:** a local LLM sometimes returns invalid structured output or is not running at all.
  The app must still produce a correct result.
- **Why:** the app should work with the model switched off.
- **Where:** each structured LLM step gets at most 3 attempts, each retry re-prompted with the specific
  error (`with_retries()` in `application/retry.py`, used by `OnboardingService` and `PlanService`); after the last failure a deterministic fallback
  produces the result (fixed questions, rule-based plan, template text). See
  [FUNCTIONAL_FLOW.md](FUNCTIONAL_FLOW.md) §0.
- **Trade-off:** the app never depends on the model, but every LLM step needs a non-LLM path.

### Tool-calling agent, ReAct-style (Agent)

- **Problem:** free-text feedback ("my knee hurt, skipped Thursday") must become structured data
  without the LLM deciding plan changes.
- **Why:** the agent can only act through our tools, so the decisions stay in our code.
- **Where:** the LangChain agent in `infrastructure/`, behind the `CoachAgent` interface, with the tools
  `get_profile`, `get_current_plan`, `submit_feedback`, `undo_last_change`. `submit_feedback` passes the
  data to the adaptation pipeline.
- **Trade-off:** new abilities are new tools, but tool calling is less reliable with a small local
  model, so the fixed questions remain as fallback.

## Patterns rejected on purpose

| Pattern | Why not |
|---|---|
| **Singleton** | Its Force is "exactly one instance … accessible from a well-known access point"; we create each object once in `main.py` and pass it in, because a global access point would block replacing `OllamaAdapter` with `FakeLLMClient` in tests. |
| **Abstract Factory** | Its Context is "multiple related families of similar objects"; we have one family (Ollama), and a second one (Groq) only exists if a laptop cannot run Ollama. |
| **Factory Method** | Its structure is a Creator whose subclasses override `FactoryMethod()`; we have no Creator hierarchy, only one place that picks a strategy, so a Simple Factory (`StrategyFactory`) is enough. |
| **Broker** | Its Context is "distributed or heterogeneous systems with independent cooperating components"; our app is a single local process. |
| **Master-Slave** | Its Context is "partitioning of work into semantically-identical sub-tasks"; our steps (safety, schedule, load) are different from each other and need no parallel work. |
| **Prototype** | Its Context is "creation of objects whose classes and properties are not known until run-time"; all our classes and fields are fixed Pydantic models. |
| **Client-Server** | Its Context is a "distributed application" with "multiple distributed clients"; our app has one user and one process, and the local Ollama server it calls is hidden behind our Adapter. |
| **Visitor** | Its Force is "object aggregate contains different interfaces"; all parts of our Composite share one interface, so the operations live in the Composite itself. |
| **Flyweight** | It shares common state between many expensive objects; our catalog has about 50 exercises, and sessions simply refer to them by `exercise_id`. |
| **MVC** | Its Force is that "the same model may need several simultaneous views"; we have one text view, and the Layers already keep the CLI free of domain logic. |
| **MOVE** | Its Context is "interactive applications with shared state, user interfaces, and workflows that may involve asynchronous tasks"; we have one synchronous text CLI, and our workflow logic already lives in the application services and the State machine. |
