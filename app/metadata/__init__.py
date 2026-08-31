from .identifier import IdentificationResult, identify, normalize_title
from .repository import MetadataRepository
from .service import MetadataResolution, MetadataService

__all__ = [
    "IdentificationResult",
    "MetadataRepository",
    "MetadataResolution",
    "MetadataService",
    "StaticMetadataProvider",
    "ProviderMetadata",
    "MetadataProvider",
    "identify",
    "normalize_title",
]
from .provider import MetadataProvider, ProviderMetadata, StaticMetadataProvider
