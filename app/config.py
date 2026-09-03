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
class JPMLConfig:
    omdb: OmdbConfig = field(default_factory=OmdbConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    player_backend: str = "vlc"


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

    return JPMLConfig(
        omdb=OmdbConfig(
            api_key=api_key,
            base_url=str(base_url),
            timeout=float(timeout),
        ),
        discovery=DiscoveryConfig(trending_provider=trending_provider),
        player_backend=player_backend,
    )
