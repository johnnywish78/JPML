from .identifier import IdentificationResult, identify, normalize_title
from .repository import MetadataRepository
from .service import MetadataResolution, MetadataService

__all__ = [
    "IdentificationResult",
    "MetadataRepository",
    "MetadataResolution",
    "MetadataService",
    "identify",
    "normalize_title",
]
