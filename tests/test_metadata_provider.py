from __future__ import annotations

import pytest

from app.metadata.provider import (
    MetadataProvider,
    ProviderMetadata,
    StaticMetadataProvider,
)


class DummyProvider(MetadataProvider):
    name = "dummy"

    def fetch_metadata(
        self,
        *,
        entity_type: str,
        external_id: str,
    ) -> ProviderMetadata | None:
        return self.normalize_metadata(
            {
                "title": "  Inception  ",
                "year": "2010",
                "overview": "A dream within a dream.",
                "genres": ["Sci-Fi", " Thriller ", ""],
                "external_id": external_id,
                "metadata_version": "v1",
            }
        )


def test_provider_metadata_is_immutable() -> None:
    metadata = ProviderMetadata(title="Inception", year=2010)

    with pytest.raises(AttributeError):
        metadata.title = "Changed"  # type: ignore[misc]


def test_normalize_metadata_returns_canonical_shape() -> None:
    provider = DummyProvider()

    metadata = provider.fetch_metadata(
        entity_type="movie",
        external_id="tt1375666",
    )

    assert metadata is not None
    assert metadata.title == "Inception"
    assert metadata.year == 2010
    assert metadata.overview == "A dream within a dream."
    assert metadata.genres == ("Sci-Fi", "Thriller")
    assert metadata.external_id == "tt1375666"
    assert metadata.metadata_version == "v1"


def test_normalize_metadata_rejects_empty_title() -> None:
    provider = DummyProvider()

    with pytest.raises(ValueError, match="metadata title"):
        provider.normalize_metadata({"title": "   "})


def test_static_provider_returns_registered_record() -> None:
    provider = StaticMetadataProvider(
        {
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "A dream within a dream.",
                "genres": ["Sci-Fi", "Thriller"],
                "external_id": "tt1375666",
            }
        }
    )

    result = provider.fetch_metadata(
        entity_type="movie",
        external_id="tt1375666",
    )

    assert result == ProviderMetadata(
        title="Inception",
        year=2010,
        overview="A dream within a dream.",
        genres=("Sci-Fi", "Thriller"),
        external_id="tt1375666",
    )


def test_static_provider_returns_none_for_unknown_record() -> None:
    provider = StaticMetadataProvider({})

    assert provider.fetch_metadata(
        entity_type="movie",
        external_id="tt9999999",
    ) is None


def test_provider_contract_requires_fetch_metadata() -> None:
    assert hasattr(MetadataProvider, "fetch_metadata")
    assert MetadataProvider.fetch_metadata.__isabstractmethod__ is True
