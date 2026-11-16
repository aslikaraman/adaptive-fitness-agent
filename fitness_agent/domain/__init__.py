"""Domain layer: pure Python models and rules of the fitness coach.

Contains the data models (UserProfile, Exercise, Feedback), the TrainingPlan
Composite, planning Strategies, the TrainingPlanBuilder, the adaptation
pipeline (Pipes & Filters) and the plan Commands with their Mementos.

Allowed imports: the standard library and pydantic only.
Must not import: any other fitness_agent layer, LangChain or Ollama.
"""
