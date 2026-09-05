from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_FILENAME = "jpml_config.json"


@dataclass(frozen=True)
class OmdbConfig:
    api_key: str = ""
    base_url: str = "https://www.omdbapi.com/"
    timeout: float = 10.0


@dataclass(frozen=True)
class DiscoveryConfig:
    trending_provider: str = "local"


@dataclass(frozen=True)
class TmdbConfig:
    api_key: str = ""
    base_url: str = "https://api.themoviedb.org/3/"
    image_base: str = "https://image.tmdb.org/t/p/w500"
    backdrop_image_base: str = "https://image.tmdb.org/t/p/w1280"
    timeout: float = 10.0


@dataclass(frozen=True)
class JPMLConfig:
    omdb: OmdbConfig = field(default_factory=OmdbConfig)
    tmdb: TmdbConfig = field(default_factory=TmdbConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    player_backend: str = "vlc"
    theme: str = "dark"


def load_config(config_path: Path | None = None) -> JPMLConfig:
    raw: dict = {}

    if config_path is None:
        config_path = _PROJECT_ROOT / _CONFIG_FILENAME

    if config_path.is_file():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}

    omdb_raw: dict = raw.get("omdb", {}) if isinstance(raw.get("omdb"), dict) else {}

    api_key = (
        omdb_raw.get("api_key")
        or os.environ.get("OMDB_API_KEY", "")
    )
    if isinstance(api_key, str):
        api_key = api_key.strip()

    base_url = omdb_raw.get("base_url", "https://www.omdbapi.com/")
    timeout = omdb_raw.get("timeout", 10.0)

    tmdb_raw: dict = raw.get("tmdb", {}) if isinstance(raw.get("tmdb"), dict) else {}

    tmdb_api_key = (
        tmdb_raw.get("api_key")
        or os.environ.get("TMDB_API_KEY", "")
    )
    if isinstance(tmdb_api_key, str):
        tmdb_api_key = tmdb_api_key.strip()

    tmdb_base_url = str(tmdb_raw.get("base_url", "https://api.themoviedb.org/3/")).strip()
    tmdb_image_base = str(tmdb_raw.get("image_base", "https://image.tmdb.org/t/p/w500")).strip()
    tmdb_backdrop_base = str(tmdb_raw.get("backdrop_image_base", "https://image.tmdb.org/t/p/w1280")).strip()
    tmdb_timeout = float(tmdb_raw.get("timeout", 10.0))

    discovery_raw: dict = (
        raw.get("discovery", {}) if isinstance(raw.get("discovery"), dict) else {}
    )
    trending_provider = str(
        discovery_raw.get("trending_provider", "local")
    ).strip().lower()
    if trending_provider not in ("local",):
        raise ValueError(
            f"Unknown discovery trending_provider: {trending_provider!r}. "
            "Supported: 'local'"
        )

    player_backend = str(raw.get("player_backend", "vlc")).strip().lower()
    theme = str(raw.get("theme", "dark")).strip().lower()
    if theme not in ("dark", "light", "system"):
        theme = "dark"

    return JPMLConfig(
        omdb=OmdbConfig(
            api_key=api_key,
            base_url=str(base_url),
            timeout=float(timeout),
        ),
        tmdb=TmdbConfig(
            api_key=tmdb_api_key,
            base_url=tmdb_base_url,
            image_base=tmdb_image_base,
            backdrop_image_base=tmdb_backdrop_base,
            timeout=tmdb_timeout,
        ),
        discovery=DiscoveryConfig(trending_provider=trending_provider),
        player_backend=player_backend,
        theme=theme,
    )


def save_config(config: JPMLConfig, config_path: Path | None = None) -> None:
    """Persist config to jpml_config.json."""
    if config_path is None:
        config_path = _PROJECT_ROOT / _CONFIG_FILENAME
    raw: dict[str, object] = {}
    if config_path.is_file():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
    raw["omdb"] = {
        "api_key": config.omdb.api_key,
        "base_url": config.omdb.base_url,
        "timeout": config.omdb.timeout,
    }
    raw["tmdb"] = {
        "api_key": config.tmdb.api_key,
        "base_url": config.tmdb.base_url,
        "image_base": config.tmdb.image_base,
        "backdrop_image_base": config.tmdb.backdrop_image_base,
        "timeout": config.tmdb.timeout,
    }
    raw["discovery"] = {
        "trending_provider": config.discovery.trending_provider,
    }
    raw["player_backend"] = config.player_backend
    raw["theme"] = config.theme
    config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
