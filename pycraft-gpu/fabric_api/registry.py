"""Centralized typed registries for Fabric API in PyCraft."""
from typing import Any, Dict, Generic, Iterator, Optional, TypeVar, Union

from fabric_api.identifier import Identifier

T = TypeVar("T")


class Registry(Generic[T]):
    """Generic typed registry with freeze/unfreeze and bidirectional mapping."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._entries: Dict[Identifier, T] = {}
        self._reverse: Dict[int, Identifier] = {}
        self._frozen: bool = False

    def register(self, identifier: Union[Identifier, str], entry: T) -> T:
        """Register an entry under the specified identifier."""
        if self._frozen:
            raise RuntimeError(f"Cannot register to frozen registry '{self.name}'")
        if isinstance(identifier, str):
            identifier = Identifier(identifier)
        self._entries[identifier] = entry
        try:
            self._reverse[id(entry)] = identifier
        except Exception:
            pass
        return entry

    def get(self, identifier: Union[Identifier, str], default: Optional[T] = None) -> Optional[T]:
        """Retrieve an entry by Identifier or string."""
        if isinstance(identifier, str):
            try:
                identifier = Identifier(identifier)
            except ValueError:
                return default
        return self._entries.get(identifier, default)

    def get_id(self, entry: T) -> Optional[Identifier]:
        """Find the Identifier registered for the given object instance."""
        return self._reverse.get(id(entry))

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, Identifier):
            return item in self._entries
        if isinstance(item, str):
            try:
                return Identifier(item) in self._entries
            except ValueError:
                return False
        return id(item) in self._reverse

    def __iter__(self) -> Iterator[T]:
        return iter(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)

    def freeze(self) -> None:
        """Lock the registry against further modifications."""
        self._frozen = True

    def unfreeze(self) -> None:
        """Unlock the registry."""
        self._frozen = False


class Registries:
    """Global registries standard across Fabric and PyCraft."""

    BLOCK: Registry[Any] = Registry("block")
    ITEM: Registry[Any] = Registry("item")
    ENTITY_TYPE: Registry[Any] = Registry("entity_type")
    SOUND_EVENT: Registry[Any] = Registry("sound_event")
    SCREEN_HANDLER: Registry[Any] = Registry("screen_handler")
    BIOME: Registry[Any] = Registry("biome")
