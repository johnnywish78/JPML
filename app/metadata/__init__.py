from .identifier import IdentificationResult, identify, normalize_title
from .repository import MetadataRepository
from .service import MetadataResolution, MetadataService

__all__ = [
    "OMDbMetadataProvider",
    "IdentificationResult",
    "MetadataRepository",
    "MetadataResolution",
    "MetadataService",
    "StaticMetadataProvider",
    "ProviderMetadata",
    "MetadataProviderRegistry",
    "MetadataProvider",
    "identify",
    "normalize_title",
]
from .registry import MetadataProviderRegistry
from .omdb_provider import OMDbMetadataProvider
from .provider import MetadataProvider, ProviderMetadata, StaticMetadataProvider
