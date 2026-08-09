"""Deterministic research-synthesis and bounded report API for Phase 9."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from financial_intelligence.api.errors import build_error_response
from financial_intelligence.application.company_resolution import QUERY_MAX_LENGTH, CompanyQuery
from financial_intelligence.application.synthesis_contracts import (
    GenerateResearchSynthesisQuery,
    SynthesisOperationStatus,
)
from financial_intelligence.application.verification_contracts import VerifyClaimQuery
from financial_intelligence.composition import AppContainer
from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CountryCode, ExchangeCode, TickerSymbol
from financial_intelligence.domain.report import ReportFormat, ResearchReportGenerationRequest
from financial_intelligence.domain.research_run import ResearchRunId
from financial_intelligence.domain.sources import SourceAuthorityTier
from financial_intelligence.domain.synthesis import (
    CitationSourceContext,
    LanguagePreference,
    MaterialClaimKind,
    MissingDataReason,
    OutputLanguage,
    ResearchSectionType,
    VerifiedClaimInput,
)
from financial_intelligence.domain.verification import (
    Claim,
    ClaimId,
    ClaimType,
    EvidenceBundle,
    EvidenceRef,
)
from financial_intelligence.observability.logging import get_logger

router = APIRouter(tags=["research-synthesis"])
logger = get_logger("financial_intelligence.api.synthesis")


class CitationSourceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=128)
    source_id: str = Field(min_length=1, max_length=128)
    provider: str | None = Field(default=None, max_length=128)
    source_name: str | None = Field(default=None, max_length=128)
    url: str | None = Field(default=None, max_length=2048)
    locator: str | None = Field(default=None, max_length=512)
    published_at: datetime | None = None
    reference_id: str | None = Field(default=None, max_length=128)
    company_id: str | None = Field(default=None, max_length=128)
    security_id: str | None = Field(default=None, max_length=128)
    listing_id: str | None = Field(default=None, max_length=128)


class SynthesisEvidenceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=128)
    source_id: str = Field(min_length=1, max_length=128)
    authority_tier: int = Field(ge=1, le=4)
    data_origin: str = Field(max_length=32)
    claim_type: str = Field(max_length=32)
    extracted_value: str | Decimal | datetime | None = None
    extracted_unit: str | None = Field(default=None, max_length=64)
    extracted_currency: str | None = Field(default=None, max_length=3)
    extracted_period: str | None = Field(default=None, max_length=64)
    as_of: datetime | None = None
    retrieved_at: datetime
    raw_snippet: str = Field(default="", max_length=2000)
    url: str | None = Field(default=None, max_length=2048)


class SynthesisClaimBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=128)
    claim_type: str = Field(max_length=32)
    text: str = Field(min_length=1, max_length=5000)
    company_id: str = Field(min_length=1, max_length=128)
    task_id: str | None = Field(default=None, max_length=128)
    section: str = Field(max_length=64)
    materiality: int = Field(default=2, ge=1, le=3)
    material_claim_kind: str = Field(default="other", max_length=64)
    security_id: str | None = Field(default=None, max_length=128)
    listing_id: str | None = Field(default=None, max_length=128)
    expected_value: str | Decimal | datetime | None = None
    expected_unit: str | None = Field(default=None, max_length=64)
    expected_currency: str | None = Field(default=None, max_length=3)
    expected_period: str | None = Field(default=None, max_length=64)
    expected_as_of: datetime | None = None
    missing_reason: str | None = Field(default=None, max_length=64)
    evidence: list[SynthesisEvidenceBody] = Field(default_factory=list, max_length=100)
    source_contexts: list[CitationSourceBody] = Field(default_factory=list, max_length=100)


class GenerateSynthesisBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(default="", max_length=QUERY_MAX_LENGTH)
    country: str | None = Field(default=None, max_length=2)
    exchange: str | None = Field(default=None, max_length=32)
    ticker: str | None = Field(default=None, max_length=32)
    research_run_id: str = Field(min_length=1, max_length=128)
    language_code: str = Field(default="en", max_length=2)
    rendering_locale: str = Field(default="en-US", max_length=5)
    claims: list[SynthesisClaimBody] = Field(min_length=1, max_length=100)
    report_format: str | None = Field(default=None, max_length=32)
    report_title: str = Field(default="Research Report", min_length=1, max_length=128)


class ResearchSynthesisResponse(BaseModel):
    operation_status: str
    status: str
    message: str
    synthesis_id: str
    research_run_id: str
    company: dict[str, Any]
    language: dict[str, Any]
    title: str
    sections: list[dict[str, Any]]
    executive_summary: dict[str, Any]
    confidence_contexts: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    missing_data: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    correlation_id: str
    generated_at: str
    kind: str
    report: dict[str, Any] | None = None


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def _company_query(body: GenerateSynthesisBody) -> CompanyQuery:
    return CompanyQuery(
        raw_query=body.q,
        country=CountryCode(body.country) if body.country else None,
        exchange=ExchangeCode(body.exchange) if body.exchange else None,
        ticker=TickerSymbol(body.ticker) if body.ticker else None,
    )


def _evidence_ref(body: SynthesisEvidenceBody) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=body.evidence_id,
        source_id=body.source_id,
        authority_tier=SourceAuthorityTier(body.authority_tier),
        data_origin=DataOrigin(body.data_origin),
        claim_type=ClaimType(body.claim_type).value,
        extracted_value=body.extracted_value,
        extracted_unit=body.extracted_unit,
        extracted_currency=body.extracted_currency,
        extracted_period=body.extracted_period,
        as_of=body.as_of,
        retrieved_at=body.retrieved_at,
        raw_snippet=body.raw_snippet,
        url=body.url,
    )


def _verified_claim(
    container: AppContainer,
    body: SynthesisClaimBody,
    research_run_id: str,
) -> VerifiedClaimInput:
    claim = Claim(
        claim_id=ClaimId.from_string(body.claim_id),
        claim_type=ClaimType(body.claim_type),
        text=body.text,
        company_id=body.company_id,
        research_run_id=research_run_id,
        task_id=body.task_id,
        expected_value=body.expected_value,
        expected_unit=body.expected_unit,
        expected_currency=body.expected_currency,
        expected_period=body.expected_period,
        expected_as_of=body.expected_as_of,
    )
    evidence_refs = tuple(_evidence_ref(item) for item in body.evidence)
    operation = container.verify_claim.execute(
        VerifyClaimQuery(claim=claim, evidence_refs=evidence_refs)
    )
    if operation.verification is None:
        raise ValueError(operation.error_message or "claim verification failed")
    return VerifiedClaimInput(
        claim=claim,
        evidence_bundle=EvidenceBundle.classify(claim, evidence_refs),
        verification=operation.verification,
        section=ResearchSectionType(body.section),
        materiality=body.materiality,
        material_claim_kind=MaterialClaimKind(body.material_claim_kind),
        security_id=body.security_id,
        listing_id=body.listing_id,
        missing_reason=(MissingDataReason(body.missing_reason) if body.missing_reason else None),
        source_contexts=tuple(
            CitationSourceContext(
                evidence_id=context.evidence_id,
                source_id=context.source_id,
                provider=context.provider,
                source_name=context.source_name,
                url=context.url,
                locator=context.locator,
                published_at=context.published_at,
                reference_id=context.reference_id,
                company_id=context.company_id,
                security_id=context.security_id,
                listing_id=context.listing_id,
            )
            for context in body.source_contexts
        ),
    )


@router.post(
    "/research/synthesis",
    response_model=ResearchSynthesisResponse,
    responses={
        400: {"description": "Invalid synthesis request"},
        409: {"description": "Company resolution or identity conflict"},
    },
)
def generate_research_synthesis(
    request: Request,
    body: GenerateSynthesisBody,
) -> ResearchSynthesisResponse | JSONResponse:
    """Verify supplied evidence and deterministically synthesize structured research."""

    container = _container(request)
    correlation_id = str(getattr(request.state, "correlation_id", "") or "")
    try:
        ResearchRunId.from_string(body.research_run_id)
        language = LanguagePreference(
            language_code=OutputLanguage(body.language_code),
            rendering_locale=body.rendering_locale,
        )
        verified_claims = tuple(
            _verified_claim(container, claim, body.research_run_id) for claim in body.claims
        )
        query = GenerateResearchSynthesisQuery(
            company_query=_company_query(body),
            research_run_id=body.research_run_id,
            verified_claims=verified_claims,
            language=language,
        )
    except (TypeError, ValueError) as exc:
        return build_error_response(
            code="invalid_synthesis_request",
            message=str(exc),
            correlation_id=correlation_id,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    result = container.generate_research_synthesis.execute(query)
    if result.status is SynthesisOperationStatus.RESOLUTION_BLOCKED:
        return build_error_response(
            code="synthesis_resolution_blocked",
            message=result.message,
            correlation_id=correlation_id,
            status_code=status.HTTP_409_CONFLICT,
        )
    if result.status is SynthesisOperationStatus.INVALID or result.synthesis is None:
        return build_error_response(
            code="invalid_synthesis_request",
            message=result.message,
            correlation_id=correlation_id,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    payload = result.synthesis.to_dict()
    report_payload: dict[str, object] | None = None
    if body.report_format is not None:
        try:
            report_format = ReportFormat(body.report_format)
            artifact = container.research_report_generator.generate(
                ResearchReportGenerationRequest(
                    synthesis_id=result.synthesis.synthesis_id,
                    report_format=report_format,
                    language=language,
                    title=body.report_title,
                ),
                result.synthesis,
            )
            report_payload = artifact.to_dict()
        except (TypeError, ValueError) as exc:
            return build_error_response(
                code="invalid_report_request",
                message=str(exc),
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    logger.info(
        "generate_research_synthesis",
        extra={
            "synthesis_status": result.synthesis.status.value,
            "claim_count": len(verified_claims),
            "section_count": len(result.synthesis.document.sections),
            "language_code": language.language_code.value,
        },
    )
    return ResearchSynthesisResponse.model_validate(
        {
            **payload,
            "operation_status": result.status.value,
            "message": result.message,
            "correlation_id": correlation_id,
            "report": report_payload,
        }
    )
