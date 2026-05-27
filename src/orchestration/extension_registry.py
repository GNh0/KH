from typing import Any, Callable, Dict, List


class ExtensionRegistry:
    def __init__(self):
        self._factories: Dict[str, Dict[str, Callable[..., Any]]] = {}

    def register(
        self,
        kind: str,
        name: str,
        factory: Callable[..., Any],
        overwrite: bool = False,
    ) -> None:
        kind_key = _normalize_key(kind)
        name_key = _normalize_key(name)
        if not callable(factory):
            raise TypeError("extension factory must be callable")

        factories = self._factories.setdefault(kind_key, {})
        if name_key in factories and not overwrite:
            raise ValueError(f"extension already registered: {kind_key}:{name_key}")
        factories[name_key] = factory

    def has(self, kind: str, name: str) -> bool:
        kind_key = _normalize_key(kind)
        name_key = _normalize_key(name)
        return name_key in self._factories.get(kind_key, {})

    def create(self, kind: str, name: str, *args, **kwargs) -> Any:
        kind_key = _normalize_key(kind)
        name_key = _normalize_key(name)
        try:
            factory = self._factories[kind_key][name_key]
        except KeyError as exc:
            raise KeyError(f"unknown extension: {kind_key}:{name_key}") from exc
        return factory(*args, **kwargs)

    def names(self, kind: str) -> List[str]:
        return sorted(self._factories.get(_normalize_key(kind), {}))


def _normalize_key(value: str) -> str:
    return str(value or "").strip().lower()
