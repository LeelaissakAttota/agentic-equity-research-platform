"""India filing/financial foundation — authority hierarchy and fixture parsing.

Live NSE/BSE/SEBI/IR HTTP acquisition is intentionally deferred: unrestricted
scraping is unsafe and exchange APIs require stable, allowlisted contracts.
Fixture payloads remain explicitly labelled fixture/demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import (
    CompanyFinancialPackage,
    FilingFormType,
    FilingId,
    FilingMetadata,
    FinancialConcept,
    FinancialDataAvailability,
    FinancialScale,
    FinancialUnit,
    IncomeStatement,
    PeriodBasis,
    ReportingPeriod,
    build_fact,
)
from financial_intelligence.domain.identity import CompanyId, CurrencyCode
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId
from financial_intelligence.infrastructure.financial.concept_mapping import (
    map_india_results_label,
)


class IndiaFilingAuthority(StrEnum):
    """Authority order for Indian disclosures (DATA_SOURCES.md Tier 1).

    Higher precedence when resolving conflicts among India sources:
    NSE exchange disclosure → BSE → SEBI → company IR.
    """

    NSE = "nse"
    BSE = "bse"
    SEBI = "sebi"
    COMPANY_IR = "company_ir"


INDIA_AUTHORITY_PRECEDENCE: tuple[IndiaFilingAuthority, ...] = (
    IndiaFilingAuthority.NSE,
    IndiaFilingAuthority.BSE,
    IndiaFilingAuthority.SEBI,
    IndiaFilingAuthority.COMPANY_IR,
)


def india_authority_rank(authority: IndiaFilingAuthority) -> int:
    """Lower rank = higher precedence."""

    return INDIA_AUTHORITY_PRECEDENCE.index(authority)


@dataclass(frozen=True, slots=True)
class IndiaResultsRow:
    """One labelled line item from an India results-style fixture payload."""

    label: str
    raw_value: Decimal
    unit: str
    scale: FinancialScale


def parse_india_results_fixture(
    payload: dict[str, Any],
    *,
    company_id: CompanyId,
    clock: datetime | None = None,
) -> CompanyFinancialPackage | None:
    """Deterministically parse an explicitly fixture-labelled India results dict.

    Expected shape (fixture only)::

        {
          "data_origin": "fixture",
          "authority": "nse",
          "currency": "INR",
          "fiscal_year": 2024,
          "period_start": "2023-04-01",
          "period_end": "2024-03-31",
          "form_type": "in_annual_results",
          "accession_or_reference": "...",
          "rows": [{"label": "Revenue from Operations", "value": "100", "scale": 1000000}]
        }
    """

    if payload.get("data_origin") != DataOrigin.FIXTURE.value:
        # Refuse to treat unlabelled / live-looking payloads as fixture success.
        return None
    authority_raw = str(payload.get("authority", "")).strip().lower()
    try:
        authority = IndiaFilingAuthority(authority_raw)
    except ValueError:
        return None
    currency_raw = payload.get("currency")
    if not isinstance(currency_raw, str) or len(currency_raw) != 3:
        return None
    try:
        fiscal_year = int(payload["fiscal_year"])
        period_start = date.fromisoformat(str(payload["period_start"]))
        period_end = date.fromisoformat(str(payload["period_end"]))
    except (KeyError, TypeError, ValueError):
        return None

    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return None

    retrieved_at = clock or datetime.now(UTC)
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=UTC)
    period = ReportingPeriod(
        basis=PeriodBasis.FISCAL_YEAR,
        fiscal_year=fiscal_year,
        period_start=period_start,
        period_end=period_end,
        label=f"FY{fiscal_year}",
    )
    currency = CurrencyCode(currency_raw.upper())
    source_id = SourceId.new()
    filing_id = FilingId.new()
    facts = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = row.get("label")
        if not isinstance(label, str):
            continue
        concept = map_india_results_label(label)
        if concept is None:
            continue
        try:
            raw = Decimal(str(row.get("value")))
            scale_int = int(row.get("scale", 1))
            scale = FinancialScale(scale_int)
        except (InvalidOperation, ValueError, KeyError, TypeError):
            continue
        if raw.is_nan() or raw.is_infinite():
            continue
        facts.append(
            build_fact(
                company_id=company_id,
                concept=concept,
                period=period,
                raw_value=raw,
                unit=FinancialUnit.CURRENCY,
                scale=scale,
                source_id=source_id,
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_at=retrieved_at,
                currency=currency,
                filing_id=filing_id,
                provider_concept=label,
            )
        )

    if not facts:
        return None

    income_concepts = {
        FinancialConcept.REVENUE,
        FinancialConcept.NET_INCOME,
        FinancialConcept.GROSS_PROFIT,
        FinancialConcept.OPERATING_INCOME,
        FinancialConcept.COST_OF_REVENUE,
        FinancialConcept.EPS_BASIC,
        FinancialConcept.EPS_DILUTED,
    }
    income_facts = tuple(f for f in facts if f.concept in income_concepts)
    if not income_facts:
        return None

    form_raw = str(payload.get("form_type", FilingFormType.IN_ANNUAL_RESULTS.value))
    try:
        form_type = FilingFormType(form_raw)
    except ValueError:
        form_type = FilingFormType.IN_ANNUAL_RESULTS

    filing = FilingMetadata(
        filing_id=filing_id,
        company_id=company_id,
        form_type=form_type,
        reporting_period=period,
        source_id=source_id,
        authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
        filed_at=period_end,
        published_at=period_end,
        retrieved_at=retrieved_at,
        accession_or_reference=(
            str(payload["accession_or_reference"])
            if payload.get("accession_or_reference")
            else None
        ),
        provider_name=f"india_fixture:{authority.value}",
    )
    return CompanyFinancialPackage(
        company_id=company_id,
        reporting_period=period,
        currency=currency,
        retrieved_at=retrieved_at,
        income_statement=IncomeStatement(
            company_id=company_id,
            period=period,
            currency=currency,
            facts=income_facts,
        ),
        filing=filing,
        provider_name=f"india_fixture:{authority.value}",
        availability=FinancialDataAvailability.PARTIAL,
        data_origin=DataOrigin.FIXTURE,
    )
