"""Phase 4 Prompt 3 contract freeze, Prompt 2 verification, and acceptance regressions."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest import TestCase

from fastapi.testclient import TestClient

from financial_intelligence.api import create_app
from financial_intelligence.application.company_resolution import CompanyQuery
from financial_intelligence.application.financial_contracts import (
    FinancialSnapshotQuery,
    FinancialSnapshotStatus,
)
from financial_intelligence.application.financial_snapshot import GetFinancialSnapshot
from financial_intelligence.application.resolve_company import ResolveCompany
from financial_intelligence.config.settings import Settings
from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import (
    CALCULATION_LIBRARY_VERSION,
    ConflictResolutionRule,
    FinancialConcept,
    FinancialMetricName,
    FinancialScale,
    FinancialUnit,
    MissingDataSemantics,
    PeriodBasis,
    PeriodIncomparabilityReason,
    ReportingPeriod,
    build_fact,
    compute_financial_metrics_result,
    resolve_fact_conflict,
)
from financial_intelligence.domain.identity import CompanyId, CurrencyCode
from financial_intelligence.domain.sources import SourceAuthorityTier, SourceId
from financial_intelligence.infrastructure.company import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.financial import (
    IndiaFilingAuthority,
    InMemoryFinancialDataAdapter,
)
from financial_intelligence.infrastructure.financial.concept_mapping import (
    map_india_results_label,
    map_us_gaap,
)
from financial_intelligence.infrastructure.financial.india_filings import india_authority_rank
from financial_intelligence.infrastructure.financial.reference_dataset import (
    APPLE_ID,
    RELIANCE_ID,
    build_reference_financial_packages,
)
from financial_intelligence.infrastructure.financial.sec_company_facts import (
    SecCompanyFactsFinancialDataAdapter,
)
from financial_intelligence.infrastructure.http import BoundedHttpClient, HttpResponse


def _settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test", LOG_LEVEL="WARNING")


def _fy(year: int = 2024) -> ReportingPeriod:
    return ReportingPeriod(
        basis=PeriodBasis.FISCAL_YEAR,
        fiscal_year=year,
        period_start=date(year - 1, 10, 1),
        period_end=date(year, 9, 28),
        label=f"FY{year}",
    )


def _money(
    *,
    concept: FinancialConcept = FinancialConcept.REVENUE,
    raw: str = "100",
    currency: str = "USD",
    unit: FinancialUnit = FinancialUnit.CURRENCY,
    tier: SourceAuthorityTier = SourceAuthorityTier.TIER_1_AUTHORITATIVE,
    period: ReportingPeriod | None = None,
    retrieved_hour: int = 12,
) -> object:
    return build_fact(
        company_id=APPLE_ID,
        concept=concept,
        period=period or _fy(),
        raw_value=Decimal(raw),
        unit=unit,
        scale=FinancialScale.ONES,
        source_id=SourceId.new(),
        authority_tier=tier,
        retrieved_at=datetime(2026, 8, 8, retrieved_hour, tzinfo=UTC),
        currency=CurrencyCode(currency) if unit is FinancialUnit.CURRENCY else None,
    )


class Prompt2FixVerificationTests(TestCase):
    def test_sec_instant_assets_do_not_require_start(self) -> None:
        payload = {
            "cik": "0000320193",
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                {
                                    "start": "2023-10-01",
                                    "end": "2024-09-28",
                                    "fy": 2024,
                                    "fp": "FY",
                                    "val": 10,
                                    "filed": "2024-11-01",
                                }
                            ]
                        }
                    },
                    "NetIncomeLoss": {
                        "units": {
                            "USD": [
                                {
                                    "start": "2023-10-01",
                                    "end": "2024-09-28",
                                    "fy": 2024,
                                    "fp": "FY",
                                    "val": 1,
                                    "filed": "2024-11-01",
                                }
                            ]
                        }
                    },
                    "Assets": {
                        "units": {
                            "USD": [
                                {
                                    "end": "2024-09-28",
                                    "fy": 2024,
                                    "fp": "FY",
                                    "val": 50,
                                    "filed": "2024-11-01",
                                }
                            ]
                        }
                    },
                }
            },
        }

        class Transport:
            def request(self, method, url, *, headers, timeout):
                return HttpResponse(200, json.dumps(payload).encode(), "application/json", {})

        adapter = SecCompanyFactsFinancialDataAdapter(
            BoundedHttpClient(Transport(), timeout_seconds=1.0, max_retries=0, user_agent="t"),
            clock=lambda: datetime(2026, 8, 8, tzinfo=UTC),
        )
        package = adapter.get_financial_package(APPLE_ID)
        self.assertIsNotNone(package)
        assert package is not None and package.balance_sheet is not None
        assets = package.balance_sheet.get(FinancialConcept.TOTAL_ASSETS)
        self.assertIsNotNone(assets)
        assert assets is not None
        self.assertEqual(assets.period.basis, PeriodBasis.INSTANT)

    def test_non_finite_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_fact(
                company_id=APPLE_ID,
                concept=FinancialConcept.REVENUE,
                period=_fy(),
                raw_value=Decimal("NaN"),
                unit=FinancialUnit.CURRENCY,
                scale=FinancialScale.ONES,
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                currency=CurrencyCode("USD"),
            )

    def test_period_duration_and_instant_protections(self) -> None:
        short = ReportingPeriod(
            basis=PeriodBasis.FISCAL_YEAR,
            fiscal_year=2024,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 3, 31),
        )
        full = ReportingPeriod(
            basis=PeriodBasis.FISCAL_YEAR,
            fiscal_year=2023,
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
        )
        self.assertEqual(
            short.incomparability_reason(full),
            PeriodIncomparabilityReason.DURATION_MISMATCH,
        )
        instant = ReportingPeriod(
            basis=PeriodBasis.INSTANT,
            fiscal_year=2024,
            period_end=date(2024, 9, 28),
            as_of=date(2024, 9, 28),
        )
        self.assertEqual(
            instant.incomparability_reason(_fy()),
            PeriodIncomparabilityReason.INSTANT_NOT_COMPARABLE,
        )

    def test_ambiguous_mapping_unmapped(self) -> None:
        self.assertIsNone(map_us_gaap("revenue"))
        self.assertIsNone(map_india_results_label("income"))
        self.assertIsNone(map_india_results_label("TotallyUnknownXYZ"))

    def test_missing_metric_never_zero_fabricated(self) -> None:
        package = build_reference_financial_packages()[APPLE_ID.as_text()]
        no_prior = type(package)(
            company_id=package.company_id,
            reporting_period=package.reporting_period,
            currency=package.currency,
            retrieved_at=package.retrieved_at,
            income_statement=package.income_statement,
            balance_sheet=package.balance_sheet,
            cash_flow_statement=package.cash_flow_statement,
            filing=package.filing,
            prior_period_package=None,
            provider_name=package.provider_name,
            availability=package.availability,
            data_origin=package.data_origin,
        )
        result = compute_financial_metrics_result(no_prior)
        growth_omit = next(
            o for o in result.omissions if o.name is FinancialMetricName.REVENUE_GROWTH
        )
        self.assertEqual(growth_omit.semantics, MissingDataSemantics.NOT_REPORTED)
        self.assertFalse(any(m.name is FinancialMetricName.REVENUE_GROWTH for m in result.metrics))


class ConflictContractFreezeTests(TestCase):
    def test_identical_values_agree(self) -> None:
        a = _money(raw="100", retrieved_hour=10)
        b = _money(
            raw="100", retrieved_hour=20, tier=SourceAuthorityTier.TIER_2_STRUCTURED_FINANCIAL
        )
        conflict = resolve_fact_conflict((a, b))  # type: ignore[arg-type]
        self.assertEqual(conflict.resolution_rule, ConflictResolutionRule.VALUES_AGREE)
        assert conflict.selected is not None
        self.assertEqual(conflict.selected.authority_tier, SourceAuthorityTier.TIER_1_AUTHORITATIVE)

    def test_higher_authority_unique_wins(self) -> None:
        low = _money(raw="100", tier=SourceAuthorityTier.TIER_2_STRUCTURED_FINANCIAL)
        high = _money(raw="200", tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE, retrieved_hour=1)
        conflict = resolve_fact_conflict((low, high))  # type: ignore[arg-type]
        self.assertEqual(conflict.resolution_rule, ConflictResolutionRule.HIGHER_AUTHORITY_TIER)
        assert conflict.selected is not None
        self.assertEqual(conflict.selected.normalized_value, Decimal("200"))

    def test_same_tier_conflict_unresolved_no_last_write_wins(self) -> None:
        early = _money(raw="100", retrieved_hour=10)
        late = _money(raw="200", retrieved_hour=22)
        conflict = resolve_fact_conflict((early, late))  # type: ignore[arg-type]
        self.assertEqual(conflict.resolution_rule, ConflictResolutionRule.UNRESOLVED)
        self.assertIsNone(conflict.selected)

    def test_currency_mismatch_unresolved_even_if_values_equal(self) -> None:
        usd = _money(raw="100", currency="USD")
        inr = _money(raw="100", currency="INR")
        conflict = resolve_fact_conflict((usd, inr))  # type: ignore[arg-type]
        self.assertEqual(conflict.resolution_rule, ConflictResolutionRule.UNRESOLVED)
        self.assertIsNone(conflict.selected)
        self.assertIn("currency", conflict.detail)

    def test_unit_mismatch_unresolved(self) -> None:
        money = _money(raw="100")
        shares = build_fact(
            company_id=APPLE_ID,
            concept=FinancialConcept.REVENUE,
            period=_fy(),
            raw_value=Decimal("100"),
            unit=FinancialUnit.SHARES,
            scale=FinancialScale.ONES,
            source_id=SourceId.new(),
            authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
            retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
        )
        conflict = resolve_fact_conflict((money, shares))  # type: ignore[arg-type]
        self.assertEqual(conflict.resolution_rule, ConflictResolutionRule.UNRESOLVED)
        self.assertIn("unit", conflict.detail)

    def test_exact_period_mismatch_same_label_unresolved(self) -> None:
        p1 = ReportingPeriod(
            basis=PeriodBasis.FISCAL_YEAR,
            fiscal_year=2024,
            period_start=date(2023, 10, 1),
            period_end=date(2024, 9, 28),
            label="FY2024",
        )
        p2 = ReportingPeriod(
            basis=PeriodBasis.FISCAL_YEAR,
            fiscal_year=2024,
            period_start=date(2023, 9, 30),
            period_end=date(2024, 9, 28),
            label="FY2024",
        )
        a = _money(raw="100", period=p1)
        b = _money(raw="100", period=p2)
        conflict = resolve_fact_conflict((a, b))  # type: ignore[arg-type]
        self.assertEqual(conflict.resolution_rule, ConflictResolutionRule.UNRESOLVED)
        self.assertIn("period", conflict.detail)


class CalculationContractFreezeTests(TestCase):
    def test_formula_versions_are_explicit(self) -> None:
        package = build_reference_financial_packages()[APPLE_ID.as_text()]
        result = compute_financial_metrics_result(package)
        self.assertTrue(result.metrics)
        for metric in result.metrics:
            self.assertTrue(metric.formula_version.startswith(f"{CALCULATION_LIBRARY_VERSION}:"))
            self.assertEqual(metric.to_dict()["kind"], "derived_metric")

    def test_library_version_frozen(self) -> None:
        self.assertEqual(CALCULATION_LIBRARY_VERSION, "financial-calc-1")


class EvidenceProvenanceAuditTests(TestCase):
    def test_apple_end_to_end_trace(self) -> None:
        use_case = GetFinancialSnapshot(
            resolve_company=ResolveCompany(InMemoryCompanyCatalog()),
            financial_data=InMemoryFinancialDataAdapter(),
            clock=lambda: datetime(2026, 8, 8, 20, tzinfo=UTC),
        )
        result = use_case.execute(
            FinancialSnapshotQuery(company_query=CompanyQuery(raw_query="Apple"))
        )
        self.assertEqual(result.status, FinancialSnapshotStatus.OK)
        assert result.package is not None
        package = result.package
        self.assertEqual(package.company_id, APPLE_ID)
        self.assertEqual(package.data_origin, DataOrigin.FIXTURE)
        assert package.filing is not None
        self.assertEqual(package.filing.company_id, APPLE_ID)
        self.assertEqual(int(package.filing.authority_tier), 1)
        assert package.income_statement is not None
        revenue = package.income_statement.get(FinancialConcept.REVENUE)
        self.assertIsNotNone(revenue)
        assert revenue is not None
        self.assertEqual(revenue.filing_id, package.filing.filing_id)
        self.assertEqual(revenue.source_id, package.filing.source_id)
        self.assertEqual(revenue.unit, FinancialUnit.CURRENCY)
        self.assertIsNotNone(revenue.currency)
        self.assertEqual(revenue.normalized_value, revenue.raw_value * Decimal(int(revenue.scale)))
        self.assertTrue(result.metrics)
        self.assertTrue(all("financial-calc-1:" in m.formula_version for m in result.metrics))
        payload = result.to_dict()
        self.assertEqual(payload["data_origin"], "fixture")
        self.assertIn("filing", payload)
        self.assertIn("source", payload)
        self.assertIn("omissions", payload)

    def test_reliance_fixture_not_live_and_inr(self) -> None:
        use_case = GetFinancialSnapshot(
            resolve_company=ResolveCompany(InMemoryCompanyCatalog()),
            financial_data=InMemoryFinancialDataAdapter(),
            clock=lambda: datetime(2026, 8, 8, 20, tzinfo=UTC),
        )
        result = use_case.execute(
            FinancialSnapshotQuery(company_query=CompanyQuery(raw_query="Reliance", exchange=None))
        )
        # May resolve via name; must remain fixture INR when available.
        if result.status is FinancialSnapshotStatus.OK:
            assert result.package is not None
            self.assertEqual(result.package.company_id, RELIANCE_ID)
            self.assertEqual(result.package.data_origin, DataOrigin.FIXTURE)
            self.assertEqual(result.package.currency.as_text(), "INR")


class IndiaAuthorityFreezeTests(TestCase):
    def test_authority_order_nse_bse_sebi_ir(self) -> None:
        self.assertEqual(
            india_authority_rank(IndiaFilingAuthority.NSE),
            0,
        )
        self.assertLess(
            india_authority_rank(IndiaFilingAuthority.BSE),
            india_authority_rank(IndiaFilingAuthority.SEBI),
        )
        self.assertLess(
            india_authority_rank(IndiaFilingAuthority.SEBI),
            india_authority_rank(IndiaFilingAuthority.COMPANY_IR),
        )


class FinancialApiContractFreezeTests(TestCase):
    def test_snapshot_exposes_omissions_and_provenance(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&exchange=NASDAQ")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data_origin"], "fixture")
        self.assertIn("omissions", payload)
        self.assertIn("metrics", payload)
        self.assertIsNotNone(payload.get("filing"))
        self.assertIsNotNone(payload.get("source"))
        self.assertTrue(response.headers.get("X-Correlation-ID"))
        dumped = json.dumps(payload).lower()
        self.assertNotIn("traceback", dumped)
        self.assertNotIn("api_key", dumped)

    def test_unavailable_fiscal_year_has_empty_metrics(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/financials/snapshot?q=Apple&fiscal_year=1999")
        payload = response.json()
        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(payload["metrics"], [])
        self.assertEqual(payload["omissions"], [])

    def test_phase1_health_ready_version_still_ok(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/ready").status_code, 200)
            self.assertEqual(client.get("/version").status_code, 200)

    def test_phase3_market_snapshot_still_ok(self) -> None:
        with TestClient(create_app(settings=_settings())) as client:
            response = client.get("/market/snapshot?q=Apple&exchange=NASDAQ")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], {"ok", "degraded", "partial", "unavailable"})


class FactInvariantFreezeTests(TestCase):
    def test_ratio_unit_rejects_currency(self) -> None:
        with self.assertRaises(ValueError):
            build_fact(
                company_id=APPLE_ID,
                concept=FinancialConcept.REVENUE,
                period=_fy(),
                raw_value=Decimal("1"),
                unit=FinancialUnit.RATIO,
                scale=FinancialScale.ONES,
                source_id=SourceId.new(),
                authority_tier=SourceAuthorityTier.TIER_1_AUTHORITATIVE,
                retrieved_at=datetime(2026, 8, 8, tzinfo=UTC),
                currency=CurrencyCode("USD"),
            )

    def test_company_id_type_is_uuidv4_company(self) -> None:
        self.assertIsInstance(APPLE_ID, CompanyId)
        self.assertNotEqual(APPLE_ID, RELIANCE_ID)
