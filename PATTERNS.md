# Design Patterns

The patterns we use, why we use them, and the patterns we rejected on purpose. Names, categories
and descriptions follow the Design Patterns lecture; each pattern is written in the lecture's
pattern format (Context, Problem, Forces, Solution, Consequences), with the Solution showing where
it lives in our code.

## Governing rule

**The LLM handles language, our code handles logic.** The LLM reads the user's words, chooses the
exercises for week 1 and explains changes; the training numbers come from our code. Every decision
(is the plan safe, does it change, by how much) is made by deterministic code, so it can be tested
without a model.

## Patterns we use

| Pattern | Lecture category | Where |
|---|---|---|
| Layers | Architecture | `fitness_agent/{interface,application,infrastructure,domain}` |
| Pipes & Filters | Architecture | `domain/adaptation.py` |
| State | Behavior | `application/states.py`, `application/session.py` |
| Strategy | Behavior | `domain/strategies.py` |
| Command | Behavior | `domain/commands.py` |
| Adapter | Wrapping | `infrastructure/ollama_adapter.py` |
| Factory Method | Creational | `StrategyFactory` in `domain/strategies.py` |
| Builder | Creational | `domain/builder.py` |
| Memento | Creational | `PlanMemento` in `domain/plan.py` |
| Composite | Collections | `domain/plan.py` |

Three further techniques are not (yet) part of the lecture and are listed after the patterns:
Template Method (a pattern from the GoF catalogue), Retry with Fallback and the tool-calling agent.

### Layers (Architecture)

- **Context:** an app with four responsibilities that change for different reasons: the user
  interface, the conversation flow, the training rules, and external details (Ollama, LangChain, JSON
  files).
- **Problem:** in the baseline they are mixed in one class, so the structure is hard to understand
  and every change touches everything.
- **Forces:** changes should be limited to one component; clear boundaries of responsibility; stable
  interfaces; parts should be exchangeable (another LLM provider, another user interface).
- **Solution:** four layers, `domain` ← `application` ← `infrastructure` ← `interface`; every layer
  only uses the defined services of the layers below (checked by import-linter). Interfaces are
  abstract base classes in `application/`; `interface/main.py` composes the layers at runtime. The
  implementation issues of the lecture are answered in [ARCHITECTURE.md](ARCHITECTURE.md).
- **Consequences:** + swapping the LLM, the storage or the user interface touches one layer (the CLI
  and the web UI share all other layers); + every layer is tested alone. − a new field (e.g. in
  `Feedback`) cascades through domain, agent tool and user interface.

### Pipes & Filters (Architecture)

- **Context:** each workout feedback is processed by the same sequence of independent rules.
- **Problem:** how to split the adaptation into several processing stages instead of one large
  function.
- **Forces:** steps should be exchangeable and reorderable; small steps are easier to reuse and test;
  safety must come before any increase.
- **Solution:** `SafetyFilter → ScheduleFilter → LoadFilter` with the common interface
  `process(context)`; `AdaptationContext` is the data format passed along the pipe; a push pipeline
  (`AdaptationPipeline.run()`). Error handling: if a filter fails, no Command is executed and the plan
  stays unchanged.
- **Consequences:** + a new rule is a new filter, testable alone; + the order is visible in one place.
  − shared information (e.g. "no increase after pain") has to travel in the context; − the order of
  the filters matters.

### State (Behavior)

- **Context:** the coach behaves differently in onboarding, plan review, feedback and adaptation.
- **Problem:** without State this becomes `if mode == ...` blocks spread over the code (the baseline's
  scattered conditionals).
- **Forces:** behaviour changes with the internal state; transitions should not depend on complex
  conditionals; states should not be mixed.
- **Solution:** `CoachSession` is the Context with `OnboardingState`, `PlanReviewState`,
  `FeedbackState`, `AdaptationState`. Each state's `handle()` returns the next state, so the states
  make the transitions; `CoachSession` only stores and calls the current one.
- **Consequences:** + a new phase is a new class; + both user interfaces get the same flow by passing
  text to `CoachSession.handle()`. − four extra classes for the flow.

### Strategy (Behavior)

- **Context:** strength, fat-loss and endurance plans differ in split, rep ranges, set limits, rest
  times and progression.
- **Problem:** a goal-based `if/else` would appear in three places: the plan skeleton, the Builder's
  limits and the adaptation guardrails.
- **Forces:** interchangeable variants of one algorithm; the same variation handled in one place.
- **Solution:** the interface `PlanningStrategy` with `StrengthStrategy`, `FatLossStrategy`,
  `EnduranceStrategy`; the callers only know the interface. `SplitStrategy` holds what the three goals
  share (see Template Method below).
- **Consequences:** + a new goal is one new class; + each goal is tested alone. − three classes
  instead of one function. A lookup table per goal would not be enough: the goals differ in behaviour,
  not only in numbers (endurance makes timed bouts longer, fat loss shortens rests).

### Command (Behavior) + Memento (Creational)

- **Context:** the plan changes after every feedback, and the user must be able to take a change back.
- **Problem:** how to make plan changes undoable and keep the plan's state restorable without
  exposing its internals.
- **Forces:** requests should be undoable; the plan should change only in controlled, logged steps;
  encapsulation must not break. The Memento slide notes that it "combines very well with Command".
- **Solution:** the filters create `SwapExerciseCommand`, `RemoveExerciseCommand`,
  `AdjustVolumeCommand`, `RescheduleCommand` with all parameters as members. `execute()` stores a
  `PlanMemento` of the `TrainingPlan` (Originator: `create_memento()`, `restore()`); each Command is
  the Caretaker of its Memento, and `undo()` restores it. The history keeps the executed Commands,
  one entry per feedback cycle.
- **Consequences:** + undo and the change history come for free; + filters only decide, Commands
  change. − more objects and one plan snapshot per change. The Memento slide's risk (a stored
  Memento manipulated "offline") does not apply: the history is kept in memory only.

### Adapter (Wrapping)

- **Context:** the app needs a language model, provided by LangChain and Ollama.
- **Problem:** their calls, output types and exceptions would leak into the application code
  ("external API details leaking into application code", Refactoring lecture).
- **Forces:** the application should not depend on one provider; tests should run without a model.
- **Solution:** `LLMClient` (target, `application/`) ← `OllamaAdapter` (adapter, `infrastructure/`)
  → `ChatOllama` (adaptee). It translates our calls into prompts and the model's output or errors
  into our types or `LLMError`. `FakeLLMClient` implements the same interface for tests.
- **Consequences:** + a new provider is one new class; + all tests run without Ollama. − one extra
  interface and translation layer.

### Factory Method (Creational)

- **Context:** the concrete Strategy is not known until runtime: it depends on the user's goal.
- **Problem:** how to create a Strategy without the callers knowing the concrete class.
- **Forces:** the callers do not care which Strategy they get, as long as it offers the same
  functionality; the class cannot be chosen at coding time; the decision is shifted to one place.
- **Solution:** the lecture's solution "define some means (method or own class) to create the actual
  object somewhere else": `StrategyFactory.create(profile)` returns a `PlanningStrategy` from a lookup
  of `goal` to class; all Strategies implement the `PlanningStrategy` interface. It is a concrete
  creator without subclasses, as one creator is enough for one product family.
- **Consequences:** + the plan service, the Builder checks and the adaptation never name a concrete
  Strategy; + a new goal is one class plus one line in the lookup. − it needs the `PlanningStrategy`
  interface.

### Builder (Creational)

- **Context:** a `TrainingPlan` is a complex object (4 weeks of sessions of exercises).
- **Problem:** it is assembled from two different sources, the LLM draft and the deterministic
  fallback, and it must be valid before anyone uses it.
- **Forces:** creation of the object should be independent of how it is assembled; many construction
  options (days, sessions, exercises per goal).
- **Solution:** `TrainingPlanBuilder` with the part methods `start_week()`, `add_session()`,
  `add_exercise()` and `build()` (the lecture's `GetResult()`). Two Directors drive the same steps:
  the plan service (LLM draft) and the Strategy (fallback week, weeks 2-4). There is one concrete
  Builder, so no abstract Builder interface.
- **Consequences:** + both creation paths share one validation: `build()` is the only way to get a
  plan and checks schema, allowed exercises, volume and structure, which answers the slide's question
  "how to ensure that parts are correctly configured?". − construction is no longer a simple "new".

### Composite (Collections)

- **Context:** a plan is a hierarchy: plan → week → session → exercise.
- **Problem:** volume, duration and intensity scaling are needed at every level.
- **Forces:** all levels should be treated uniformly; one call should reach all parts.
- **Solution:** `TrainingPlan`, `Week`, `Session` (composites) and `PlannedExercise` (leaf), all with
  `total_volume()`, `duration()` and `scale_intensity(factor)`.
- **Consequences:** + the same call works on a whole plan or one session (e.g. the deload week).
  − a call on the plan is hidden work on every exercise.

## Further techniques (not covered by the lecture)

### Template Method (Behavior, GoF)

- **Context:** several classes run the same steps in the same order and differ in one step.
- **Problem:** written in each class, the shared steps would be copied (the duplication smell).
- **Solution:** a base class fixes the order and the subclasses implement one step:
  `PlanCommand.execute()` stores the Memento, then calls `_apply()`, which each Command implements, and
  `undo()` is written once; `AskingState` fixes ask → validate → re-ask, and `OnboardingState` and
  `FeedbackState` add their questions and next state; `SplitStrategy` fixes the split, the fallback
  week and the progression, and each goal supplies its numbers.
- **Consequences:** + a new Command cannot forget the Memento. − the subclasses share a base class.

### Retry with Fallback

- **Context:** a local LLM sometimes returns invalid structured output or is not running at all.
- **Solution:** each structured LLM step gets at most 3 attempts, each retry re-prompted with the
  specific error (`with_retries()` in `application/retry.py`); after the last failure a deterministic
  fallback produces the result (fixed questions, rule-based plan, template text).
  See [FUNCTIONAL_FLOW.md](FUNCTIONAL_FLOW.md) §0.
- **Consequences:** + the app works with the model switched off. − every LLM step needs a non-LLM path.

### Tool-calling agent (ReAct-style)

- **Context:** free-text feedback ("my knee hurt, skipped Thursday") must become structured data.
- **Solution:** a LangChain agent behind the `CoachAgent` interface with the tools `get_profile`,
  `get_current_plan`, `submit_feedback`, `undo_last_change`; it can only act through these tools, so
  the decisions stay in our code.
- **Consequences:** + new abilities are new tools. − tool calling is less reliable with a small local
  model, so the fixed questions remain as fallback.

## Refactoring from the baseline

The naive baseline (git tag `v0-baseline`, one file) shows the code smells of the Refactoring lecture.
Each step removed some of them by introducing a pattern, while the behaviour stayed the same
(Rahul's scenario tests check the same rules end to end).

| Code smell | In the baseline | Change | Commit |
|---|---|---|---|
| Large classes | `FitnessCoach` holds profile, plan, rules, LLM calls, storage and CLI | Layers; domain models and the Composite; services, states, filters | `3db5269`, `b069233`, `ceac8ca` |
| Scattered conditionals | `if self.mode == ...`, `if p["goal"] == ...`, `if lt == "kg" ...` | State; Strategy per goal; the load type in the leaf, one rounding rule | `b069233`, `ceac8ca`, `3db5269` |
| Duplication | the prompt header, the 3-attempt loop and the "apply to all remaining sessions" loop are copied | one prompt module; `with_retries()` and `AskingState`; the Commands with Template Method | `f71c9da`, `b069233`, `ceac8ca` |
| Tight coupling | LangChain, JSON files and `input()`/`print()` inside the rules | Adapter and the interfaces of the application layer | `f71c9da`, `b069233` |
| Difficult testing | a rule only runs inside the interactive loop with a model | fakes for every interface; the tests run without a model | all steps |


## Patterns rejected on purpose

"Patterns are tools, not rules": each pattern below was checked against its Context and Forces
from the lecture and left out because they do not fit our app.

| Pattern | Why not |
|---|---|
| **Singleton** | Its Force is "exactly one instance … accessible from a well-known access point"; we create each object once in `main.py` and pass it in, because a global access point would block replacing `OllamaAdapter` with `FakeLLMClient` in tests. |
| **Abstract Factory** | Its Context is "multiple related families of similar objects"; we have one family (Ollama), and a second one (Groq) only exists if a laptop cannot run Ollama. |
| **Prototype** | Its Context is "creation of objects whose classes and properties are not known until run-time"; all our classes and fields are fixed Pydantic models. |
| **Flyweight** | It shares common state between many expensive objects; our catalog has about 50 exercises, and sessions simply refer to them by `exercise_id`. |
| **Decorator** | Its design pressure is "many combinations of optional behavior"; our behaviours are not combined: each goal is one Strategy and each rule one filter. |
| **Visitor** | Its Force is "object aggregate contains different interfaces"; all parts of our Composite share one interface, so the operations live in the Composite itself. |
| **Broker** | Its Context is "distributed or heterogeneous systems with independent cooperating components"; our app is a single local process. |
| **Master-Slave** | Its Context is "partitioning of work into semantically-identical sub-tasks"; our steps (safety, schedule, load) are different from each other and need no parallel work. |
| **Client-Server** | Its Context is a "distributed application" with "multiple distributed clients"; the web UI runs on Gradio's local web server and Ollama is a local server too, but both are frameworks we use, not a design we build: there is one user, and the Forces (a limited service shared by many requesters, an unknown number of clients) do not apply. |
| **MVC** | Its Forces ("domain logic independent of the user interface", "several simultaneous views") are met by Layers and State: the CLI and the web UI are two views; the plan panel (`plan_view.py`) presents the model's state by querying it, and the current State interprets the input. What MVC adds, a Controller per view and the Model notifying its observers, is not needed: the request/response cycle redraws the page after every input, so nothing has to be notified. |
| **MVP** | Its central idea is a Presenter per view that "explicitly updates the View"; with one page and no presentation logic beyond rendering the plan, a Presenter would only forward calls ("many forwarding methods"). |
| **MVVM** | It synchronizes the View with a ViewModel "through bindings or reactive observation"; Gradio has no bindings to a model object, and the panel is simply re-rendered after each input. |
| **BLoC** | Its View sends events and renders the states a BLoC emits as observable streams; our views send text to `CoachSession` and read the result once per request, so there are no streams, subscriptions or concurrent events to coordinate. |
| **MOVE** | Its Context is "workflows that may involve asynchronous tasks" with events connecting the parts; our workflows run synchronously, one input at a time, and already live in the application services and the State machine. |
