# External Resources

All libraries, models, tools and other resources used in this project. Everything is free.

## Python libraries (runtime)

| Library | Version | License | Used for |
|---|---|---|---|
| [LangChain](https://github.com/langchain-ai/langchain) | 1.5.0 | MIT | Agent framework |
| [langchain-ollama](https://github.com/langchain-ai/langchain) | 1.1.0 | MIT | Connects LangChain to the local Ollama models |
| [Pydantic](https://github.com/pydantic/pydantic) | 2.14.3 | MIT | Data models and validation of LLM output |

## Python libraries (development and metrics)

| Library | Version | License | Used for |
|---|---|---|---|
| [pytest](https://github.com/pytest-dev/pytest) | 9.2.0 | MIT | Tests |
| [pytest-cov](https://github.com/pytest-dev/pytest-cov) | 7.1.0 | MIT | Test coverage |
| [pylint / pyreverse](https://github.com/pylint-dev/pylint) | 4.1.4 | GPL-2.0-or-later | Class diagram generated from the code |
| [radon](https://github.com/rubik/radon) | 6.0.1 | MIT | Cyclomatic complexity |
| [cohesion](https://github.com/mschwager/cohesion) | 1.2.0 | GPL-3.0 | Class cohesion (LCOM) |
| [import-linter](https://github.com/seddonym/import-linter) | 2.16 | BSD-2-Clause | Checking layer rules (coupling) |
| [pydeps](https://github.com/thebjorn/pydeps) | 3.0.9 | BSD-2-Clause | Import graph |
| [interrogate](https://github.com/econchick/interrogate) | 1.7.0 | MIT | Docstring coverage |

The development tools are only run on our code; they are not part of the application.

## Models and runtime

| Resource | License | Used for |
|---|---|---|
| [Ollama](https://github.com/ollama/ollama) | MIT | Runs the LLMs locally |
| [Qwen3 8B](https://huggingface.co/Qwen/Qwen3-8B) (`qwen3`) | Apache-2.0 | Main LLM |
| [Qwen3 4B](https://huggingface.co/Qwen/Qwen3-4B) (`qwen3:4b`) | Apache-2.0 | Model comparison for the validity metric |

## Other tools

| Tool | Used for |
|---|---|
| Visual Paradigm | UML class and sequence diagrams |
| [Mermaid](https://mermaid.js.org) (MIT, rendered by GitHub) | Sketch diagrams in the Markdown documents |
| Claude Code (Anthropic) | AI assistance, see [AI_USAGE.md](AI_USAGE.md) |

## Images and visualizations in the slides

_To be added when the slides are made._
