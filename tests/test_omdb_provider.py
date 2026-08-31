from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.config import JPMLConfig, OmdbConfig, load_config
from app.metadata.omdb_provider import OMDbMetadataProvider


class TestConfigLoading:
    def test_load_config_defaults(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "nonexistent.json")
        assert config.omdb.api_key == ""
        assert config.omdb.base_url == "https://www.omdbapi.com/"
        assert config.omdb.timeout == 10.0

    def test_load_config_from_file(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "jpml_config.json"
        cfg_file.write_text('{"omdb": {"api_key": "test123", "timeout": 5.0}}')

        config = load_config(cfg_file)
        assert config.omdb.api_key == "test123"
        assert config.omdb.timeout == 5.0

    def test_load_config_env_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OMDB_API_KEY", "env_key_123")
        config = load_config(tmp_path / "nonexistent.json")
        assert config.omdb.api_key == "env_key_123"

    def test_load_config_file_takes_precedence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OMDB_API_KEY", "env_key")
        cfg_file = tmp_path / "jpml_config.json"
        cfg_file.write_text('{"omdb": {"api_key": "file_key"}}')

        config = load_config(cfg_file)
        assert config.omdb.api_key == "file_key"

    def test_load_config_malformed_json(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "jpml_config.json"
        cfg_file.write_text("{invalid json")

        config = load_config(cfg_file)
        assert config.omdb.api_key == ""

    def test_load_config_empty_omdb_section(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "jpml_config.json"
        cfg_file.write_text('{"omdb": {}}')

        config = load_config(cfg_file)
        assert config.omdb.api_key == ""
        assert config.omdb.base_url == "https://www.omdbapi.com/"


class TestOmdbProviderConfig:
    def test_config_object_used(self) -> None:
        cfg = OmdbConfig(api_key="cfg_key", timeout=5.0)
        provider = OMDbMetadataProvider(config=cfg)
        assert provider.api_key == "cfg_key"
        assert provider.timeout == 5.0

    def test_direct_api_key_still_works(self) -> None:
        provider = OMDbMetadataProvider(api_key="direct_key")
        assert provider.api_key == "direct_key"

    def test_env_fallback_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OMDB_API_KEY", "env_key")
        provider = OMDbMetadataProvider()
        assert provider.api_key == "env_key"

    def test_config_overrides_direct_params(self) -> None:
        cfg = OmdbConfig(api_key="cfg_key", base_url="https://custom.api/", timeout=3.0)
        provider = OMDbMetadataProvider(
            api_key="direct_key",
            base_url="https://other.api/",
            timeout=99.0,
            config=cfg,
        )
        assert provider.api_key == "cfg_key"
        assert provider.base_url == "https://custom.api/"
        assert provider.timeout == 3.0

    def test_api_key_never_in_error_message(self) -> None:
        provider = OMDbMetadataProvider(api_key="")
        with pytest.raises(ValueError, match="OMDB_API_KEY is required"):
            provider.fetch_metadata(entity_type="movie", external_id="tt123")

    def test_api_key_not_in_invalid_id_error(self) -> None:
        provider = OMDbMetadataProvider(api_key="my_secret_key")
        try:
            provider.fetch_metadata(entity_type="movie", external_id="12345")
        except ValueError as e:
            assert "my_secret_key" not in str(e)

    def test_empty_key_treated_as_missing(self) -> None:
        provider = OMDbMetadataProvider(api_key="  ")
        with pytest.raises(ValueError, match="OMDB_API_KEY is required"):
            provider.fetch_metadata(entity_type="movie", external_id="tt123")


class TestOmdbProviderWithFakeSession:
    def test_successful_fetch(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": "True",
            "Title": "Inception",
            "Year": "2010",
            "Genre": "Action,Sci-Fi",
            "Plot": "A dream within a dream.",
        }
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        result = provider.fetch_metadata(entity_type="movie", external_id="tt1375666")

        assert result is not None
        assert result.title == "Inception"
        assert result.year == 2010
        assert result.genres == ("Action", "Sci-Fi")
        assert result.external_id == "tt1375666"

    def test_response_false(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"Response": "False", "Error": "Movie not found"}
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        result = provider.fetch_metadata(entity_type="movie", external_id="tt999")
        assert result is None

    def test_malformed_json(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("No JSON")
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        result = provider.fetch_metadata(entity_type="movie", external_id="tt123")
        assert result is None

    def test_missing_title(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": "True",
            "Year": "2024",
            "Genre": "Action",
            "Plot": "A movie.",
        }
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        result = provider.fetch_metadata(entity_type="movie", external_id="tt123")
        assert result is None

    def test_empty_genres(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": "True",
            "Title": "Test",
            "Year": "2024",
            "Genre": "",
            "Plot": "A movie.",
        }
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        result = provider.fetch_metadata(entity_type="movie", external_id="tt123")
        assert result is not None
        assert result.genres == ()

    def test_year_range_parsing(self) -> None:
        assert OMDbMetadataProvider._parse_year("2008–2013") == 2008
        assert OMDbMetadataProvider._parse_year("2024") == 2024
        assert OMDbMetadataProvider._parse_year(None) is None
        assert OMDbMetadataProvider._parse_year("abc") is None

    def test_http_failure_propagates(self) -> None:
        import requests as req

        mock_session = MagicMock()
        mock_session.get.side_effect = req.ConnectionError("timeout")

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        with pytest.raises(req.ConnectionError):
            provider.fetch_metadata(entity_type="movie", external_id="tt123")

    def test_tv_entity_type_accepted(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": "True",
            "Title": "Breaking Bad",
            "Year": "2008",
            "Genre": "Drama,Crime",
            "Plot": "A teacher turns to crime.",
        }
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        result = provider.fetch_metadata(entity_type="tv", external_id="tt0903747")
        assert result is not None
        assert result.title == "Breaking Bad"

    def test_unsupported_entity_type(self) -> None:
        provider = OMDbMetadataProvider(api_key="test_key")
        result = provider.fetch_metadata(entity_type="person", external_id="nm123")
        assert result is None

    def test_api_key_not_exposed_in_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("boom")

        provider = OMDbMetadataProvider(api_key="SUPER_SECRET_KEY", session=mock_session)

        with caplog.at_level(logging.WARNING):
            try:
                provider.fetch_metadata(entity_type="movie", external_id="tt123")
            except Exception:
                pass

        for record in caplog.records:
            assert "SUPER_SECRET_KEY" not in record.getMessage()
