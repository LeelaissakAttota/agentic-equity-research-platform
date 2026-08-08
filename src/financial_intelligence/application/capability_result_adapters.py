"""Narrow adapters from Phase 2-5 snapshot results to TaskExecutionResult.

Phase 2-5 modules must not import orchestration; dependency flows downward only.
"""

from __future__ import annotations

from financial_intelligence.application.company_resolution import ResolutionResult, ResolutionStatus
from financial_intelligence.application.financial_contracts import (
    FinancialSnapshotResult,
    FinancialSnapshotStatus,
)
from financial_intelligence.application.industry_contracts import (
    IndustrySnapshotResult,
    IndustrySnapshotStatus,
)
from financial_intelligence.application.market_contracts import (
    MarketSnapshotResult,
    MarketSnapshotStatus,
)
from financial_intelligence.application.news_event_contracts import (
    NewsEventSnapshotResult,
    NewsEventSnapshotStatus,
)
from financial_intelligence.application.regulatory_contracts import (
    RegulatorySnapshotResult,
    RegulatorySnapshotStatus,
)
from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.identity import CompanyId, CompanyIdentity
from financial_intelligence.domain.orchestration import (
    TaskEvidenceRef,
    TaskExecutionResult,
    TaskId,
    TaskResultStatus,
)
from financial_intelligence.domain.sources import SourceMetadata


def _identity_mismatch(
    task_id: TaskId,
    *,
    expected: CompanyId,
    actual: CompanyId | None,
) -> TaskExecutionResult:
    return TaskExecutionResult(
        task_id=task_id,
        status=TaskResultStatus.FAILED,
        message=(
            f"capability company identity mismatch: expected={expected.as_text()} "
            f"actual={actual.as_text() if actual is not None else 'none'}"
        ),
        retryable=False,
        error_code="identity_mismatch",
    )


def _check_resolved_company(
    task_id: TaskId,
    *,
    expected: CompanyId,
    resolution: ResolutionResult | None,
) -> TaskExecutionResult | None:
    if resolution is None:
        return None
    if resolution.status is not ResolutionStatus.RESOLVED or resolution.company is None:
        return TaskExecutionResult(
            task_id=task_id,
            status=TaskResultStatus.FAILED,
            message=resolution.message or "company resolution did not remain unique",
            retryable=False,
            error_code="identity_mismatch",
        )
    if resolution.company.company_id != expected:
        return _identity_mismatch(task_id, expected=expected, actual=resolution.company.company_id)
    return None


def _evidence_from_source(
    *,
    company_id: CompanyId,
    source: SourceMetadata | None,
    data_origin: DataOrigin | None = None,
) -> tuple[TaskEvidenceRef, ...]:
    if source is None:
        return (TaskEvidenceRef(company_id=company_id, data_origin=data_origin),)
    return (
        TaskEvidenceRef(
            company_id=source.company_id or company_id,
            source_id=source.source_id,
            authority_tier=source.authority_tier,
            data_origin=data_origin,
            security_id=source.security_id,
            listing_id=source.listing_id,
            as_of=source.published_at,
            retrieved_at=source.retrieved_at,
            locator=source.url,
        ),
    )


def _terminal_codes(mapped: TaskResultStatus) -> tuple[bool, str | None]:
    if mapped is TaskResultStatus.FAILED:
        return False, "invalid_input"
    if mapped is TaskResultStatus.UNAVAILABLE:
        return False, "unavailable"
    if mapped is TaskResultStatus.BLOCKED:
        return False, "blocked_dependency"
    return False, None


def adapt_resolution_result(
    task_id: TaskId,
    *,
    expected: CompanyId,
    resolution: ResolutionResult,
    company: CompanyIdentity,
) -> TaskExecutionResult:
    mismatch = _check_resolved_company(task_id, expected=expected, resolution=resolution)
    if mismatch is not None:
        return mismatch
    return TaskExecutionResult(
        task_id=task_id,
        status=TaskResultStatus.SUCCESS,
        message="company identity confirmed for plan execution",
        evidence_refs=(TaskEvidenceRef(company_id=company.company_id),),
        output_summary=f"company_id={company.company_id.as_text()}",
        retryable=False,
    )


def adapt_market_result(
    task_id: TaskId,
    *,
    expected: CompanyId,
    result: MarketSnapshotResult,
) -> TaskExecutionResult:
    mismatch = _check_resolved_company(task_id, expected=expected, resolution=result.resolution)
    if mismatch is not None:
        return mismatch
    status_map = {
        MarketSnapshotStatus.OK: TaskResultStatus.SUCCESS,
        MarketSnapshotStatus.PARTIAL: TaskResultStatus.PARTIAL,
        MarketSnapshotStatus.DEGRADED: TaskResultStatus.PARTIAL,
        MarketSnapshotStatus.UNAVAILABLE: TaskResultStatus.UNAVAILABLE,
        MarketSnapshotStatus.RESOLUTION_BLOCKED: TaskResultStatus.BLOCKED,
        MarketSnapshotStatus.INVALID: TaskResultStatus.FAILED,
    }
    mapped = status_map[result.status]
    data_origin = result.series.data_origin if result.series is not None else None
    evidence = (
        _evidence_from_source(company_id=expected, source=result.source, data_origin=data_origin)
        if mapped in {TaskResultStatus.SUCCESS, TaskResultStatus.PARTIAL}
        else ()
    )
    retryable, error_code = _terminal_codes(mapped)
    summary = None
    if result.series is not None:
        origin_text = data_origin.value if data_origin is not None else None
        summary = (
            f"market status={result.status.value} origin={origin_text} "
            f"freshness={result.freshness.value} "
            f"observations={len(result.series.bars)}"
        )
    return TaskExecutionResult(
        task_id=task_id,
        status=mapped,
        message=result.message,
        evidence_refs=evidence,
        output_summary=summary,
        retryable=retryable,
        error_code=error_code,
    )


def adapt_financial_result(
    task_id: TaskId,
    *,
    expected: CompanyId,
    result: FinancialSnapshotResult,
) -> TaskExecutionResult:
    mismatch = _check_resolved_company(task_id, expected=expected, resolution=result.resolution)
    if mismatch is not None:
        return mismatch
    status_map = {
        FinancialSnapshotStatus.OK: TaskResultStatus.SUCCESS,
        FinancialSnapshotStatus.PARTIAL: TaskResultStatus.PARTIAL,
        FinancialSnapshotStatus.DEGRADED: TaskResultStatus.PARTIAL,
        FinancialSnapshotStatus.UNAVAILABLE: TaskResultStatus.UNAVAILABLE,
        FinancialSnapshotStatus.RESOLUTION_BLOCKED: TaskResultStatus.BLOCKED,
        FinancialSnapshotStatus.INVALID: TaskResultStatus.FAILED,
    }
    mapped = status_map[result.status]
    data_origin = result.package.data_origin if result.package is not None else None
    evidence: tuple[TaskEvidenceRef, ...] = ()
    if (
        mapped in {TaskResultStatus.SUCCESS, TaskResultStatus.PARTIAL}
        and result.package is not None
    ):
        pkg = result.package
        if pkg.filing is not None:
            evidence = (
                TaskEvidenceRef(
                    company_id=expected,
                    source_id=pkg.filing.source_id,
                    authority_tier=pkg.filing.authority_tier,
                    data_origin=data_origin,
                    security_id=pkg.security_id,
                    listing_id=pkg.listing_id,
                    retrieved_at=pkg.filing.retrieved_at or pkg.retrieved_at,
                    locator=pkg.filing.source_url,
                ),
            )
        else:
            evidence = (
                TaskEvidenceRef(
                    company_id=expected,
                    data_origin=data_origin,
                    security_id=pkg.security_id,
                    listing_id=pkg.listing_id,
                    retrieved_at=pkg.retrieved_at,
                ),
            )
    retryable, error_code = _terminal_codes(mapped)
    origin_text = data_origin.value if data_origin is not None else None
    summary = (
        f"financial status={result.status.value} metrics={len(result.metrics)} "
        f"omissions={len(result.omissions)} origin={origin_text}"
    )
    return TaskExecutionResult(
        task_id=task_id,
        status=mapped,
        message=result.message,
        evidence_refs=evidence,
        output_summary=summary,
        retryable=retryable,
        error_code=error_code,
    )


def adapt_news_result(
    task_id: TaskId,
    *,
    expected: CompanyId,
    result: NewsEventSnapshotResult,
) -> TaskExecutionResult:
    mismatch = _check_resolved_company(task_id, expected=expected, resolution=result.resolution)
    if mismatch is not None:
        return mismatch
    status_map = {
        NewsEventSnapshotStatus.OK: TaskResultStatus.SUCCESS,
        NewsEventSnapshotStatus.PARTIAL: TaskResultStatus.PARTIAL,
        NewsEventSnapshotStatus.DEGRADED: TaskResultStatus.PARTIAL,
        NewsEventSnapshotStatus.UNAVAILABLE: TaskResultStatus.UNAVAILABLE,
        NewsEventSnapshotStatus.RESOLUTION_BLOCKED: TaskResultStatus.BLOCKED,
        NewsEventSnapshotStatus.INVALID: TaskResultStatus.FAILED,
    }
    mapped = status_map[result.status]
    package = result.package
    evidence: tuple[TaskEvidenceRef, ...] = ()
    if mapped in {TaskResultStatus.SUCCESS, TaskResultStatus.PARTIAL} and package is not None:
        refs: list[TaskEvidenceRef] = [
            TaskEvidenceRef(
                company_id=expected,
                data_origin=package.data_origin,
                retrieved_at=package.retrieved_at,
            )
        ]
        for event in package.events[:12]:
            refs.append(
                TaskEvidenceRef(
                    company_id=expected,
                    source_id=event.evidence.source_id,
                    authority_tier=event.evidence.authority_tier,
                    data_origin=package.data_origin,
                    retrieved_at=event.evidence.retrieved_at,
                    locator=event.evidence.source_url or event.evidence.locator,
                )
            )
        evidence = tuple(refs)
    retryable, error_code = _terminal_codes(mapped)
    event_count = len(package.events) if package is not None else 0
    return TaskExecutionResult(
        task_id=task_id,
        status=mapped,
        message=result.message,
        evidence_refs=evidence,
        output_summary=f"news status={result.status.value} events={event_count}",
        retryable=retryable,
        error_code=error_code,
    )


def adapt_industry_result(
    task_id: TaskId,
    *,
    expected: CompanyId,
    result: IndustrySnapshotResult,
) -> TaskExecutionResult:
    mismatch = _check_resolved_company(task_id, expected=expected, resolution=result.resolution)
    if mismatch is not None:
        return mismatch
    status_map = {
        IndustrySnapshotStatus.OK: TaskResultStatus.SUCCESS,
        IndustrySnapshotStatus.PARTIAL: TaskResultStatus.PARTIAL,
        IndustrySnapshotStatus.DEGRADED: TaskResultStatus.PARTIAL,
        IndustrySnapshotStatus.UNAVAILABLE: TaskResultStatus.UNAVAILABLE,
        IndustrySnapshotStatus.RESOLUTION_BLOCKED: TaskResultStatus.BLOCKED,
        IndustrySnapshotStatus.INVALID: TaskResultStatus.FAILED,
    }
    mapped = status_map[result.status]
    package = result.package
    evidence: tuple[TaskEvidenceRef, ...] = ()
    if mapped in {TaskResultStatus.SUCCESS, TaskResultStatus.PARTIAL} and package is not None:
        evidence = (
            TaskEvidenceRef(
                company_id=expected,
                data_origin=package.data_origin,
                retrieved_at=package.retrieved_at,
            ),
        )
    retryable, error_code = _terminal_codes(mapped)
    return TaskExecutionResult(
        task_id=task_id,
        status=mapped,
        message=result.message,
        evidence_refs=evidence,
        output_summary=f"industry status={result.status.value}",
        retryable=retryable,
        error_code=error_code,
    )


def adapt_regulatory_result(
    task_id: TaskId,
    *,
    expected: CompanyId,
    result: RegulatorySnapshotResult,
) -> TaskExecutionResult:
    mismatch = _check_resolved_company(task_id, expected=expected, resolution=result.resolution)
    if mismatch is not None:
        return mismatch
    status_map = {
        RegulatorySnapshotStatus.OK: TaskResultStatus.SUCCESS,
        RegulatorySnapshotStatus.PARTIAL: TaskResultStatus.PARTIAL,
        RegulatorySnapshotStatus.DEGRADED: TaskResultStatus.PARTIAL,
        RegulatorySnapshotStatus.UNAVAILABLE: TaskResultStatus.UNAVAILABLE,
        RegulatorySnapshotStatus.RESOLUTION_BLOCKED: TaskResultStatus.BLOCKED,
        RegulatorySnapshotStatus.INVALID: TaskResultStatus.FAILED,
    }
    mapped = status_map[result.status]
    package = result.package
    evidence: tuple[TaskEvidenceRef, ...] = ()
    if mapped in {TaskResultStatus.SUCCESS, TaskResultStatus.PARTIAL} and package is not None:
        evidence = (
            TaskEvidenceRef(
                company_id=expected,
                data_origin=package.data_origin,
                retrieved_at=package.retrieved_at,
            ),
        )
    retryable, error_code = _terminal_codes(mapped)
    return TaskExecutionResult(
        task_id=task_id,
        status=mapped,
        message=result.message,
        evidence_refs=evidence,
        output_summary=f"regulatory status={result.status.value}",
        retryable=retryable,
        error_code=error_code,
    )
