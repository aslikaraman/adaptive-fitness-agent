"""Composition root: the only place that creates the concrete objects.

It builds the infrastructure implementations (e.g. OllamaAdapter, JSON
storage), passes them into the application layer through its interfaces, and
starts the CLI. No other module chooses a concrete implementation.

Run with:  python -m fitness_agent.interface.main
"""


def main() -> None:
    """Wire the layers together and start the CLI."""
    print("Adaptive Fitness Agent: not implemented yet.")


if __name__ == "__main__":
    main()
