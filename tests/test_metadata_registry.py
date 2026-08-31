from __future__ import annotations

import pytest

from app.metadata.provider import StaticMetadataProvider
from app.metadata.registry import MetadataProviderRegistry


def test_registry_registers_and_returns_provider() -> None:
    registry = MetadataProviderRegistry()
    provider = StaticMetadataProvider(
        {"movie:tt1375666": {"title": "Inception", "year": 2010}}
    )

    registry.register(provider)

    assert registry.has("static")
    assert registry.get("static") is provider
    assert registry.names() == ("static",)


def test_registry_rejects_duplicate_provider_name() -> None:
    registry = MetadataProviderRegistry()
    registry.register(StaticMetadataProvider({}))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(StaticMetadataProvider({}))


def test_registry_reports_unknown_provider() -> None:
    registry = MetadataProviderRegistry()

    with pytest.raises(KeyError, match="not registered"):
        registry.get("tmdb")


def test_registry_names_are_sorted() -> None:
    first = StaticMetadataProvider({})
    first.name = "static"  # type: ignore[misc]

    registry = MetadataProviderRegistry()
    registry.register(first)

    assert registry.names() == ("static",)
