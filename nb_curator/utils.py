"""Utility functions for nb-curator."""

from typing import List
from ruamel.yaml import YAML


def get_yaml() -> YAML:
    """Return configured ruamel.yaml instance."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def remove_common_prefix(strings: List[str]) -> List[str]:
    """Remove common prefix from a list of strings."""
    if not strings:
        return []

    # Find the shortest string to avoid index out of range
    shortest = min(strings, key=len)
    prefix_length = 0

    for i in range(len(shortest)):
        if all(s.startswith(shortest[: i + 1]) for s in strings):
            prefix_length = i + 1
        else:
            break

    # Remove the common prefix
    return [s[prefix_length:] for s in strings]


def create_divider(title: str, char: str = "*", width: int = 100) -> str:
    """Create a divider string with centered title."""
    return f" {title} ".center(width, char) + "\n"
