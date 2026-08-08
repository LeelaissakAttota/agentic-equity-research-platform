"""Industry/competitor reference fixtures (Phase 5 Prompt 2 foundation).

REFERENCE / DEMO only — not live industry databases.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId
from financial_intelligence.domain.industry import (
    CompanyIndustryPackage,
    CompetitorRelationship,
    IndustryAvailability,
    IndustryClassification,
    IndustryTaxonomySource,
    PeerResolutionState,
    RelationshipDirection,
)
from financial_intelligence.domain.news.events import EventEvidenceRef, InformationClass
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId

_RETRIEVED = datetime(2026, 8, 8, 18, 0, tzinfo=UTC)
APPLE_ID = CompanyId.from_string("22222222-2222-4222-8222-222222222001")
MICROSOFT_ID = CompanyId.from_string("22222222-2222-4222-8222-222222222002")
RELIANCE_ID = CompanyId.from_string("11111111-1111-4111-8111-111111111001")
TCS_ID = CompanyId.from_string("11111111-1111-4111-8111-111111111002")

_APPLE_SRC = SourceId(value=UUID("84333333-3333-4333-8333-333333333001"))
_RELIANCE_SRC = SourceId(value=UUID("84333333-3333-4333-8333-333333333002"))


def _evidence(source_id: SourceId, locator: str, *, published: date) -> EventEvidenceRef:
    return EventEvidenceRef(
        source_id=source_id,
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        locator=locator,
        retrieved_at=_RETRIEVED,
        published_at=published,
        provider_name="fixture",
        source_url=None,
    )


def build_reference_industry_packages() -> dict[str, CompanyIndustryPackage]:
    apple = CompanyIndustryPackage(
        company_id=APPLE_ID,
        retrieved_at=_RETRIEVED,
        industry=IndustryClassification(
            company_id=APPLE_ID,
            canonical_code="consumer_electronics",
            canonical_label="Consumer Electronics",
            provider_label="Technology Hardware",
            taxonomy_source=IndustryTaxonomySource.REFERENCE,
            evidence=_evidence(_APPLE_SRC, "fixture:industry:apple", published=date(2024, 1, 1)),
        ),
        competitors=(
            CompetitorRelationship(
                subject_company_id=APPLE_ID,
                peer_display_name="Microsoft",
                peer_resolution=PeerResolutionState.RESOLVED,
                peer_company_id=MICROSOFT_ID,
                evidence=_evidence(
                    _APPLE_SRC, "fixture:competitor:apple:msft", published=date(2024, 3, 1)
                ),
                as_of=date(2024, 3, 1),
                direction=RelationshipDirection.BIDIRECTIONAL,
                information_class=InformationClass.RESEARCH_FINDING,
            ),
            CompetitorRelationship(
                subject_company_id=APPLE_ID,
                peer_display_name="Unresolved Handset Peer",
                peer_resolution=PeerResolutionState.UNRESOLVED,
                evidence=EventEvidenceRef(
                    source_id=SourceId(value=UUID("84333333-3333-4333-8333-333333333091")),
                    authority_tier=SourceAuthorityTier.TIER_3_REPUTABLE_NEWS,
                    locator="fixture:competitor:apple:unresolved",
                    retrieved_at=_RETRIEVED,
                    published_at=date(2024, 4, 1),
                    provider_name="fixture",
                ),
                as_of=date(2024, 4, 1),
                information_class=InformationClass.OPINION,
            ),
        ),
        provider_name="fixture",
        availability=IndustryAvailability.AVAILABLE,
        data_origin=DataOrigin.FIXTURE,
    )

    reliance = CompanyIndustryPackage(
        company_id=RELIANCE_ID,
        retrieved_at=_RETRIEVED,
        industry=IndustryClassification(
            company_id=RELIANCE_ID,
            canonical_code="diversified_conglomerate",
            canonical_label="Diversified Conglomerate",
            provider_label="Oil Gas and Consumer",
            taxonomy_source=IndustryTaxonomySource.REFERENCE,
            evidence=_evidence(
                _RELIANCE_SRC, "fixture:industry:reliance", published=date(2024, 1, 1)
            ),
        ),
        competitors=(
            CompetitorRelationship(
                subject_company_id=RELIANCE_ID,
                peer_display_name="TCS",
                peer_resolution=PeerResolutionState.RESOLVED,
                peer_company_id=TCS_ID,
                evidence=_evidence(
                    _RELIANCE_SRC,
                    "fixture:competitor:reliance:tcs-note",
                    published=date(2024, 2, 1),
                ),
                as_of=date(2024, 2, 1),
                information_class=InformationClass.RESEARCH_FINDING,
            ),
        ),
        provider_name="fixture",
        availability=IndustryAvailability.AVAILABLE,
        data_origin=DataOrigin.FIXTURE,
    )
    return {
        APPLE_ID.as_text(): apple,
        RELIANCE_ID.as_text(): reliance,
    }
