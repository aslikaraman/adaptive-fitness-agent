# Design Patterns

This document lists the patterns we use, why we use them, and the patterns we rejected on purpose.
Pattern names, Context and Forces follow the lecture slides (Behavioral, Creational, Architectural,
GUI and Refactoring decks). For every pattern we also answer the lecture's question:
*which change is easier now, and what complexity did we add?*

The full entries in the lecture format (Name, Context, Problem, Forces, Solution, Consequences,
Known Uses, plus UML and file/class) are added once the code exists. Class names below are the planned
ones from [FUNCTIONAL_FLOW.md](FUNCTIONAL_FLOW.md).

## Governing rule

**The LLM handles language, our code handles logic.** The LLM reads the user's words, drafts the
week-1 plan and explains changes. Every decision (is the plan safe, does it change, by how much) is
made by deterministic code, so it can be tested without a model.

## Patterns we use

### Layers (Architectural)

- **Problem here:** the app mixes four responsibilities that change for different reasons: the CLI,
  the conversation flow, the training rules, and external details (Ollama, LangChain, JSON files).
- **Why this pattern (slide):** *Forces:* "changes should be limited to one component", "parts should
  be exchangeable" (e.g. another LLM provider), "interfaces should be stable". Our app is small, so
  we use only four layers.
- **Where:** `fitness_agent/domain`, `application`, `infrastructure`, `interface`; rules in
  `pyproject.toml`, see [ARCHITECTURE.md](ARCHITECTURE.md).
- **Slide questions:** *Who composes the layers at runtime?* `interface/main.py` (composition root).
  *How are interfaces defined?* As abstract base classes in `application/`.
- **Easier / cost:** swapping the LLM or the storage touches one layer. Cost: a new field (e.g. in
  `Feedback`) can cascade through domain, agent tool and CLI (the slide's "changes cascade").

### State (Behavioral)

- **Problem here:** the coach behaves differently in onboarding, plan review, feedback and adaptation.
  In the baseline this becomes `if mode == ...` blocks spread over the code.
- **Why this pattern (slide):** *Forces:* "behaviour should change with internal state", "transition
  between states should not depend on complex multipart conditional statements", "states should not be
  mixed". The Refactoring deck maps "scattered state-dependent behavior" to State.
- **Where:** `CoachSession` (Context) with `OnboardingState`, `PlanReviewState`, `FeedbackState`,
  `AdaptationState`.
- **Slide question:** *Who makes the transitions?* Each state's `handle()` returns the next state;
  `CoachSession` only stores and calls the current one.
- **Easier / cost:** a new phase is a new class. Cost: four extra classes for a flow that is mostly linear.

### Adapter (Wrapping)

- **Problem here:** LangChain/Ollama calls, their output types and their exceptions would otherwise leak
  into the application code and make it untestable without a running model.
- **Why this pattern (slide):** the Refactoring deck maps "external API details leaking into
  application code" to Adapter, with the intended improvement "isolate an external interface".
- **Where:** `LLMClient` (target interface, `application/`) ← `OllamaAdapter` (adapter,
  `infrastructure/`) → `ChatOllama` from langchain-ollama (adaptee). `FakeLLMClient` implements the same
  interface for tests.
- **Easier / cost:** changing provider or model is one new class; tests run without Ollama. Cost: one
  interface plus one translation layer.

### Strategy, chosen by a Simple Factory (Behavioral)

- **Problem here:** strength, fat-loss and endurance plans differ in rep ranges, set limits, rest
  times and progression. The goal-based `if/else` would appear in three places: the plan skeleton, the
  Builder's limits and the adaptation guardrails.
- **Why this pattern (slide):** *Context:* "many related classes which differ only in their
  behaviour", "methods with complex behaviour based on many conditionals"; *Force:* "you need different
  variants for an algorithm". The Refactoring deck's smell "scattered conditionals: the same variation
  is handled in multiple places" is exactly this.
- **Where:** `PlanningStrategy` (interface) with `StrengthStrategy`, `FatLossStrategy`,
  `EnduranceStrategy`.
- **Slide question:** *Who assembles the concrete strategies at runtime?* `StrategyFactory.create(profile)`,
  a lookup from `goal` to strategy class. This is a **Simple Factory**: one concrete class, not the
  Factory Method structure from the slides (see "Rejected" below).
- **Easier / cost:** a new goal is one new class plus one line in the factory (our scalability metric).
  Cost: three classes and a factory instead of one function.
- **Guard against over-engineering:** the strategies must differ in *behaviour* (split template,
  progression rule, fallback exercise selection), not only in numbers. If they end up differing only in
  numbers, one data table per goal replaces them (Refactoring deck: "a function, conditional, or lookup
  table may be sufficient").

### Composite (Behavioral)

- **Problem here:** a plan is a hierarchy: plan → week → session → exercise. Volume, duration and
  intensity scaling are needed at every level.
- **Why this pattern (slide):** *Forces:* "treat all object-granularities uniformly", "apply/reroute a
  method call to all objects".
- **Where:** `TrainingPlan`, `Week`, `Session` (composites) and `PlannedExercise` (leaf), all with
  `total_volume()`, `duration()`, `scale_intensity(factor)`.
- **Easier / cost:** the same call works on a whole plan or one session. Cost: the slide's "high call
  hierarchy"; a call on the plan is hidden work on every exercise.

### Builder (Creational)

- **Problem here:** a `TrainingPlan` is a complex object that is assembled from two different sources,
  the LLM draft and the deterministic fallback, and it must be valid before anyone uses it.
- **Why this pattern (slide):** *Context:* "creation of complex objects"; *Force:* "creation of objects
  should be independent of assembling".
- **Where:** `TrainingPlanBuilder` with `start_week()`, `add_session()`, `add_exercise()`, `build()`. Two
  callers direct it: the plan service (LLM draft) and the Strategy (fallback, weeks 2–4).
- **Slide question:** *How to ensure that parts are correctly configured?* `build()` is the only way to get
  a `TrainingPlan` and runs the validation gate (schema, allowed pool, volume, structure).
- **Easier / cost:** both creation paths share one validation. Cost: construction is no longer a simple
  constructor call. If only one caller remains in the code, we drop the Builder.

### Pipes & Filters (Architectural)

- **Problem here:** each feedback goes through the same sequence of independent rules: safety first,
  then schedule, then load.
- **Why this pattern (slide):** *Forces:* "exchanging or reordering of processing steps shall be
  possible", "small processing steps are easier to reuse than larger". The slide's solution steps match
  what we need: a defined data format along the pipe (`AdaptationContext`) and designed error handling.
  The slide's *Context* is "processing of data streams"; our stream is the sequence of feedback entries,
  each processed by the same pipeline. The multiprocessing force does not apply to us.
- **Where:** `SafetyFilter → ScheduleFilter → LoadFilter`, common `process(context)` interface.
- **Error handling:** if a filter fails, no Command is executed and the plan stays unchanged.
- **Easier / cost:** a new rule is a new filter, testable alone. Cost: shared information has to travel in
  the context object (the slide's "sharing state infos is expensive"), and the order of the filters matters.

### Command + Memento (Behavioral + Creational)

- **Problem here:** the user must be able to undo an adaptation, and the plan must only change in
  controlled, logged steps.
- **Why this pattern (slide):** Command's *Force:* "a request should be undoable", consequence
  "undo/redo-operations become possible". Memento: "state can be persisted without exposing all internal
  members", and the slide notes it "combines very well with Command Pattern".
- **Where:** filters create `SwapExerciseCommand`, `AdjustVolumeCommand`, `RescheduleCommand` (with all
  parameters as members); `execute()` stores a `PlanMemento` of the `TrainingPlan` (originator), `undo()`
  restores it; the history of feedback cycles is the caretaker.
- **Easier / cost:** undo and the change history come for free; filters only *decide*, Commands *change*.
  Cost: more objects, and every change stores a plan snapshot.

### Template Method (Behavioral)

- **Problem here:** all three Commands must do the same thing around their change: store a Memento
  before changing the plan and restore it on undo. Written in each Command, this code would be copied
  three times (Cut-and-Paste Programming, the anti-pattern named in the course slides).
- **Why this pattern (slide):** "define methods and let children implement the behaviour": the parent
  fixes the order of steps, the children fill in one step.
- **Where:** abstract `PlanCommand.execute(plan)` (template method) stores the `PlanMemento`, then calls
  `_apply(plan)` (primitive operation), which each concrete Command implements; `undo()` is written once
  in `PlanCommand`.
- **Easier / cost:** a new Command only implements `_apply()` and cannot forget the Memento. Cost: the
  Commands share a base class (inheritance instead of composition).

## Patterns from outside the lecture

These are not in the lecture slides, but our design depends on them, so we name them.

### Retry with Fallback (resilience pattern)

- **Problem here:** a local LLM sometimes returns invalid structured output or is not running at all.
  The app must still produce a correct result.
- **Solution:** each structured LLM step gets at most 3 attempts, each retry re-prompted with the
  specific error; after the last failure a deterministic fallback produces the result (fixed questions,
  rule-based plan, template text). See [FUNCTIONAL_FLOW.md](FUNCTIONAL_FLOW.md) §0.
- **Where:** the retry loop in the application services; the fallbacks in the states and the Strategy.
- **Easier / cost:** the app works with the model switched off, and the validity metric counts how often
  the fallback was needed. Cost: every LLM step needs a non-LLM path.

### Tool-calling agent (ReAct-style)

- **Problem here:** the task asks for an agentic system; free-text feedback ("my knee hurt, skipped
  Thursday") must become structured data without the LLM deciding plan changes.
- **Solution:** the LangChain agent reasons over the user's text and calls our tools (`get_profile`,
  `get_current_plan`, `submit_feedback`, `undo_last_change`). The tools are the only way it can act, and
  `submit_feedback` passes the data to the deterministic pipeline.
- **Where:** the agent in `infrastructure/`, behind the `CoachAgent` interface.
- **Easier / cost:** new abilities are new tools. Cost: tool calling is less reliable with a small local
  model, so the fixed questions remain as fallback.

## Patterns rejected on purpose

| Pattern | Why not (based on the slide's Context / Forces) |
|---|---|
| **Singleton** | Its Force is "exactly one instance … accessible from a well-known access point"; we create each object once in `main.py` and pass it in, because a global access point would block replacing `OllamaAdapter` with `FakeLLMClient` in tests. |
| **Abstract Factory** | Its Context is "multiple related families of similar objects"; we have one family (Ollama), and a second one (Groq) only exists if a laptop cannot run Ollama. |
| **Factory Method** | Its structure is a Creator whose subclasses override `FactoryMethod()`; we have no Creator hierarchy, only one place that picks a strategy, so a Simple Factory (`StrategyFactory`) is enough. |
| **Broker** | Its Context is "distributed or heterogeneous systems with independent cooperating components"; our app is a single local process. |
| **Master-Slave** | Its Context is "partitioning of work into semantically-identical sub-tasks"; our steps (safety, schedule, load) are different from each other and need no parallel work. |
| **Prototype** | Its Context is "creation of objects whose classes and properties are not known until run-time"; all our classes and fields are fixed Pydantic models (copying a plan for a Memento is a normal deep copy). |
| **Client-Server** | Its Context is a "distributed application" with "multiple distributed clients"; our app has one user and one process, and the local Ollama server it calls is Ollama's design, hidden behind our Adapter. |
| **Visitor** | Its Force is "object aggregate contains different interfaces"; all parts of our Composite share one interface, so the operations live in the Composite itself. |
| **Flyweight** | Its idea is to "share global state and vary differences only when needed" for many expensive objects (the slide's examples are game assets and pre-rendered glyphs); our catalog has about 50 exercises, and sessions simply refer to them by `exercise_id`. |
| **MVC** | Its Forces are "the same model may need several simultaneous views" and independently changeable presentation; we have one text view, and the Layers already keep the CLI free of domain logic. |
| **MOVE** | Its Context is "interactive applications with shared state, user interfaces, and workflows that may involve asynchronous tasks"; we have one synchronous text CLI, and our workflow logic already has a home in the application services and the State machine. |

## Lecture decks checked

Behavioral, Creational, Architectural, GUI and Refactoring decks, checked on 2026-11-16. When a new deck
arrives, this pattern set is checked against it.
