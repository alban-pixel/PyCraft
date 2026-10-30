"""Fabric Identifier implementation with validation and string parsing."""
import re
from typing import Optional, Union


class Identifier:
    """Namespaced resource identifier in format 'namespace:path'."""

    _NAMESPACE_REGEX = re.compile(r"^[a-z0-9_.-]+$")
    _PATH_REGEX = re.compile(r"^[a-z0-9_./-]+$")

    __slots__ = ("namespace", "path")

    def __init__(self, namespace_or_string: str, path: Optional[str] = None) -> None:
        if path is None:
            if ":" in namespace_or_string:
                ns, p = namespace_or_string.split(":", 1)
                self.namespace = ns
                self.path = p
            else:
                self.namespace = "minecraft"
                self.path = namespace_or_string
        else:
            self.namespace = namespace_or_string
            self.path = path

        self._validate()

    def _validate(self) -> None:
        if not self._NAMESPACE_REGEX.match(self.namespace):
            raise ValueError(
                f"Invalid namespace '{self.namespace}': must be non-empty lowercase alphanumeric, '_', '.', or '-'"
            )
        if not self._PATH_REGEX.match(self.path):
            raise ValueError(
                f"Invalid path '{self.path}': must be non-empty lowercase alphanumeric, '_', '.', '/', or '-'"
            )

    def __str__(self) -> str:
        return f"{self.namespace}:{self.path}"

    def __repr__(self) -> str:
        return f"Identifier('{self.namespace}', '{self.path}')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Identifier):
            return self.namespace == other.namespace and self.path == other.path
        if isinstance(other, str):
            try:
                parsed = Identifier(other)
                return self.namespace == parsed.namespace and self.path == parsed.path
            except ValueError:
                return False
        return False

    def __hash__(self) -> int:
        return hash((self.namespace, self.path))
