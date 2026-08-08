"""Optional SEC EDGAR company-facts HTTP adapter (Tier-1 structured data).

Uses the public ``data.sec.gov`` XBRL companyfacts JSON endpoint. No API key.
Automated tests must inject a fake transport — CI never depends on live SEC.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import (
    BalanceSheet,
    CompanyFinancialPackage,
    FilingFormType,
    FilingId,
    FilingMetadata,
    FinancialConcept,
    FinancialDataAvailability,
    FinancialFact,
    FinancialScale,
    FinancialUnit,
    IncomeStatement,
    PeriodBasis,
    ReportingPeriod,
    build_fact,
    detect_fact_conflicts,
)
from financial_intelligence.domain.identity import CompanyId, CurrencyCode
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId
from financial_intelligence.infrastructure.financial.concept_mapping import map_us_gaap
from financial_intelligence.infrastructure.financial.sec_cik_mapping import sec_cik_for_company
from financial_intelligence.infrastructure.http import BoundedHttpClient, HttpTransportError
from financial_intelligence.observability.logging import get_logger

logger = get_logger("financial_intelligence.infrastructure.financial.sec_company_facts")

_SEC_COMPANYFACTS_BASE = "https://data.sec.gov/api/xbrl/companyfacts/"
_SEC_ALLOWED_HOST = "data.sec.gov"

# Duration (income) vs instant (balance) concept tags.
_DURATION_TAGS: tuple[tuple[str, FinancialConcept], ...] = (
    ("Revenues", FinancialConcept.REVENUE),
    ("RevenueFromContractWithCustomerExcludingAssessedTax", FinancialConcept.REVENUE),
    ("NetIncomeLoss", FinancialConcept.NET_INCOME),
    ("GrossProfit", FinancialConcept.GROSS_PROFIT),
    ("OperatingIncomeLoss", FinancialConcept.OPERATING_INCOME),
)
_INSTANT_TAGS: tuple[tuple[str, FinancialConcept], ...] = (
    ("Assets", FinancialConcept.TOTAL_ASSETS),
    ("AssetsCurrent", FinancialConcept.CURRENT_ASSETS),
    ("LiabilitiesCurrent", FinancialConcept.CURRENT_LIABILITIES),
    ("StockholdersEquity", FinancialConcept.SHAREHOLDERS_EQUITY),
)


class SecCompanyFactsFinancialDataAdapter:
    """Live FinancialDataPort adapter for SEC companyfacts JSON."""

    provider_name = "sec_company_facts"

    def __init__(
        self,
        http: BoundedHttpClient,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._http = http
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_financial_package(
        self,
        company_id: CompanyId,
        *,
        fiscal_year: int | None = None,
    ) -> CompanyFinancialPackage | None:
        cik = sec_cik_for_company(company_id)
        if cik is None:
            return None
        url = f"{_SEC_COMPANYFACTS_BASE}CIK{cik}.json"
        if not self._is_allowlisted_url(url):
            logger.warning(
                "sec_company_facts_url_rejected",
                extra={"company_id": company_id.as_text()},
            )
            return None
        try:
            payload = self._http.get_json(url)
        except HttpTransportError as exc:
            logger.warning(
                "sec_company_facts_failed",
                extra={
                    "company_id": company_id.as_text(),
                    "status": exc.status_code,
                    "error_type": type(exc).__name__,
                    "failure_kind": exc.kind.value,
                },
            )
            return None
        except Exception as exc:
            logger.warning(
                "sec_company_facts_error",
                extra={
                    "company_id": company_id.as_text(),
                    "error_type": type(exc).__name__,
                },
            )
            return None
        if not isinstance(payload, dict):
            return None
        return self._parse_package(company_id, payload, fiscal_year=fiscal_year, cik=cik)

    @staticmethod
    def _is_allowlisted_url(url: str) -> bool:
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == _SEC_ALLOWED_HOST
            and parsed.path.startswith("/api/xbrl/companyfacts/")
        )

    def _parse_package(
        self,
        company_id: CompanyId,
        payload: dict[str, Any],
        *,
        fiscal_year: int | None,
        cik: str,
    ) -> CompanyFinancialPackage | None:
        facts_root = payload.get("facts", {})
        if not isinstance(facts_root, dict):
            return None
        us_gaap = facts_root.get("us-gaap", {})
        if not isinstance(us_gaap, dict) or not us_gaap:
            return None

        retrieved_at = self._clock()
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=UTC)

        source_id = SourceId.new()
        filing_id = FilingId.new()
        currency = CurrencyCode("USD")
        fact_rows: list[FinancialFact] = []
        seen_concepts: set[FinancialConcept] = set()

        # Prefer first successful alias per concept — avoid false conflicts from synonyms.
        for tag, default_concept in _DURATION_TAGS:
            if default_concept in seen_concepts:
                continue
            fact = self._extract_fact(
                us_gaap=us_gaap,
                tag=tag,
                default_concept=default_concept,
                company_id=company_id,
                fiscal_year=fiscal_year,
                source_id=source_id,
                filing_id=filing_id,
                retrieved_at=retrieved_at,
                currency=currency,
                require_start=True,
            )
            if fact is not None:
                fact_rows.append(fact)
                seen_concepts.add(fact.concept)

        for tag, default_concept in _INSTANT_TAGS:
            if default_concept in seen_concepts:
                continue
            fact = self._extract_fact(
                us_gaap=us_gaap,
                tag=tag,
                default_concept=default_concept,
                company_id=company_id,
                fiscal_year=fiscal_year,
                source_id=source_id,
                filing_id=filing_id,
                retrieved_at=retrieved_at,
                currency=currency,
                require_start=False,
            )
            if fact is not None:
                fact_rows.append(fact)
                seen_concepts.add(fact.concept)

        if not fact_rows:
            return None

        survivors, conflicts = detect_fact_conflicts(fact_rows)

        # Prefer a duration FY period for the package when available.
        duration_facts = [f for f in survivors if f.period.basis is PeriodBasis.FISCAL_YEAR]
        if not duration_facts:
            return None
        reporting_period = max(
            (f.period for f in duration_facts),
            key=lambda p: p.selection_key(),
        )
        # Keep only facts whose fiscal year matches the selected package period.
        aligned = [
            f
            for f in survivors
            if f.period.fiscal_year == reporting_period.fiscal_year
            and (
                f.period == reporting_period
                or (
                    f.period.basis is PeriodBasis.INSTANT
                    and f.period.period_end == reporting_period.period_end
                )
            )
        ]
        if not aligned:
            return None

        income_concepts = {
            FinancialConcept.REVENUE,
            FinancialConcept.NET_INCOME,
            FinancialConcept.GROSS_PROFIT,
            FinancialConcept.OPERATING_INCOME,
        }
        income_facts = tuple(
            f for f in aligned if f.concept in income_concepts and f.period == reporting_period
        )
        if not income_facts:
            return None

        balance_period = ReportingPeriod(
            basis=PeriodBasis.INSTANT,
            fiscal_year=reporting_period.fiscal_year,
            period_end=reporting_period.period_end,
            as_of=reporting_period.period_end,
            label=f"BS{reporting_period.fiscal_year}",
        )
        balance_concepts = {
            FinancialConcept.TOTAL_ASSETS,
            FinancialConcept.CURRENT_ASSETS,
            FinancialConcept.CURRENT_LIABILITIES,
            FinancialConcept.SHAREHOLDERS_EQUITY,
        }
        balance_facts = tuple(
            build_fact(
                company_id=f.company_id,
                concept=f.concept,
                period=balance_period,
                raw_value=f.raw_value,
                unit=f.unit,
                scale=f.scale,
                source_id=f.source_id,
                authority_tier=f.authority_tier,
                retrieved_at=f.retrieved_at,
                currency=f.currency,
                filing_id=f.filing_id,
                provider_concept=f.provider_concept,
            )
            for f in aligned
            if f.concept in balance_concepts
        )

        accession = payload.get("cik")
        accession_text = str(accession).strip() if accession is not None else None
        filing = FilingMetadata(
            filing_id=filing_id,
            company_id=company_id,
            form_type=FilingFormType.US_10K,
            reporting_period=reporting_period,
            source_id=source_id,
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            filed_at=reporting_period.period_end,
            published_at=reporting_period.period_end,
            retrieved_at=retrieved_at,
            accession_or_reference=accession_text or cik,
            source_url=f"{_SEC_COMPANYFACTS_BASE}CIK{cik}.json",
            provider_name=self.provider_name,
        )
        income = IncomeStatement(
            company_id=company_id,
            period=reporting_period,
            currency=currency,
            facts=income_facts,
        )
        balance = (
            BalanceSheet(
                company_id=company_id,
                period=balance_period,
                currency=currency,
                facts=balance_facts,
            )
            if balance_facts
            else None
        )
        return CompanyFinancialPackage(
            company_id=company_id,
            reporting_period=reporting_period,
            currency=currency,
            retrieved_at=retrieved_at,
            income_statement=income,
            balance_sheet=balance,
            filing=filing,
            provider_name=self.provider_name,
            availability=FinancialDataAvailability.PARTIAL,
            data_origin=DataOrigin.LIVE,
            conflicts=conflicts,
        )

    def _extract_fact(
        self,
        *,
        us_gaap: dict[str, Any],
        tag: str,
        default_concept: FinancialConcept,
        company_id: CompanyId,
        fiscal_year: int | None,
        source_id: SourceId,
        filing_id: FilingId,
        retrieved_at: datetime,
        currency: CurrencyCode,
        require_start: bool,
    ) -> FinancialFact | None:
        mapped = map_us_gaap(tag) or default_concept
        entry = us_gaap.get(tag)
        if not isinstance(entry, dict):
            return None
        units = entry.get("units", {})
        if not isinstance(units, dict):
            return None
        usd_rows = units.get("USD")
        if not isinstance(usd_rows, list):
            # Unsupported / non-USD units are skipped (no fabricated conversion).
            return None
        fy_row = self._select_fy_row(usd_rows, fiscal_year=fiscal_year, require_start=require_start)
        if fy_row is None:
            return None
        val = fy_row.get("val")
        if val is None:
            return None
        try:
            normalized = Decimal(str(val))
        except (InvalidOperation, ValueError):
            return None
        if normalized.is_nan() or normalized.is_infinite():
            return None
        end_raw = fy_row.get("end")
        if not isinstance(end_raw, str):
            return None
        try:
            period_end = date.fromisoformat(end_raw)
            fy = int(fy_row.get("fy", period_end.year))
        except (TypeError, ValueError):
            return None
        start_raw = fy_row.get("start")
        if require_start:
            if not isinstance(start_raw, str):
                return None
            try:
                period_start = date.fromisoformat(start_raw)
            except ValueError:
                return None
            period = ReportingPeriod(
                basis=PeriodBasis.FISCAL_YEAR,
                fiscal_year=fy,
                period_start=period_start,
                period_end=period_end,
                label=f"FY{fy}",
            )
        else:
            period = ReportingPeriod(
                basis=PeriodBasis.INSTANT,
                fiscal_year=fy,
                period_end=period_end,
                as_of=period_end,
                label=f"BS{fy}",
            )
        return build_fact(
            company_id=company_id,
            concept=mapped,
            period=period,
            raw_value=normalized,
            unit=FinancialUnit.CURRENCY,
            scale=FinancialScale.ONES,
            source_id=source_id,
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=retrieved_at,
            currency=currency,
            filing_id=filing_id,
            provider_concept=tag,
        )

    @staticmethod
    def _select_fy_row(
        rows: list[Any],
        *,
        fiscal_year: int | None,
        require_start: bool,
    ) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            fp = row.get("fp")
            if fp != "FY":
                continue
            if require_start and not isinstance(row.get("start"), str):
                continue
            if not isinstance(row.get("end"), str):
                continue
            if row.get("val") is None:
                continue
            candidates.append(row)
        if not candidates:
            return None
        if fiscal_year is not None:
            year_matches = []
            for row in candidates:
                try:
                    if int(row.get("fy", 0)) == fiscal_year:
                        year_matches.append(row)
                except (TypeError, ValueError):
                    continue
            candidates = year_matches
            if not candidates:
                return None
        # Prefer later filed/amended observation when present; never invent values.
        return max(
            candidates,
            key=lambda r: (
                str(r.get("filed", "")),
                str(r.get("end", "")),
                int(r.get("fy", 0)) if str(r.get("fy", "")).isdigit() else 0,
            ),
        )
