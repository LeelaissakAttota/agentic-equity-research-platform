"""Provider-neutral domain primitives.

Domain code must remain free of FastAPI, providers, and infrastructure SDKs.
"""

from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.domain.sources import (
    SourceAuthorityTier,
    SourceId,
    SourceMetadata,
    SourceType,
)

__all__ = [
    "ResearchRunId",
    "SourceAuthorityTier",
    "SourceId",
    "SourceMetadata",
    "SourceType",
]
