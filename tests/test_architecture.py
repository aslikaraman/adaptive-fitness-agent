"""Checks the layer rules of the Layers pattern (see ARCHITECTURE.md).

The contracts are defined in pyproject.toml under [tool.importlinter].
"""

from importlinter.cli import EXIT_STATUS_SUCCESS, lint_imports


def test_layer_contracts_are_kept():
    """Dependencies point inward only, and domain/application never import LangChain."""
    assert lint_imports(no_cache=True, no_logo=True) == EXIT_STATUS_SUCCESS
