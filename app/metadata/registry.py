from __future__ import annotations

from .provider import MetadataProvider


class MetadataProviderRegistry:
    """Registry of named metadata providers."""

    def __init__(self) -> None:
        self._providers: dict[str, MetadataProvider] = {}

    def register(self, provider: MetadataProvider) -> None:
        name = provider.name.strip()
        if not name:
            raise ValueError("provider name must not be empty")
        if name in self._providers:
            raise ValueError(f"metadata provider already registered: {name}")
        self._providers[name] = provider

    def get(self, name: str) -> MetadataProvider:
        try:
            return self._providers[name]
        except KeyError as exc:
            raise KeyError(f"metadata provider not registered: {name}") from exc

    def has(self, name: str) -> bool:
        return name in self._providers

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
