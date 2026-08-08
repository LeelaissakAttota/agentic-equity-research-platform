"""Concept mapping, India foundation, filing pipeline, cache/fallback tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Thread
from unittest import TestCase

from financial_intelligence.application.filing_pipeline import (
    FilingPipelineStage,
    assemble_package_from_facts,
)
from financial_intelligence.domain.data_origin import DataOrigin
from financial_intelligence.domain.financial import (
    FinancialConcept,
)
from financial_intelligence.infrastructure.financial import (
    CachingFinancialDataAdapter,
    FallbackFinancialDataAdapter,
    IndiaFilingAuthority,
    InMemoryFinancialDataAdapter,
    parse_india_results_fixture,
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


class ConceptMappingTests(TestCase):
    def test_us_gaap_aliases(self) -> None:
        self.assertEqual(map_us_gaap("Revenues"), FinancialConcept.REVENUE)
        self.assertEqual(
            map_us_gaap("RevenueFromContractWithCustomerExcludingAssessedTax"),
            FinancialConcept.REVENUE,
        )
        self.assertEqual(map_us_gaap("netincomeloss"), FinancialConcept.NET_INCOME)

    def test_india_whitespace_normalization(self) -> None:
        self.assertEqual(
            map_india_results_label("  Revenue   from Operations "),
            FinancialConcept.REVENUE,
        )

    def test_unknown_and_ambiguous_do_not_map(self) -> None:
        self.assertIsNone(map_us_gaap("TotallyUnknownTagXYZ"))
        self.assertIsNone(map_india_results_label("income"))
        self.assertIsNone(map_india_results_label("profit"))
        self.assertIsNone(map_us_gaap("revenue"))  # too short/ambiguous


class IndiaFilingFoundationTests(TestCase):
    def test_authority_precedence(self) -> None:
        self.assertLess(
            india_authority_rank(IndiaFilingAuthority.NSE),
            india_authority_rank(IndiaFilingAuthority.BSE),
        )
        self.assertLess(
            india_authority_rank(IndiaFilingAuthority.SEBI),
            india_authority_rank(IndiaFilingAuthority.COMPANY_IR),
        )

    def test_fixture_parser_requires_fixture_origin(self) -> None:
        payload = {
            "data_origin": "live",
            "authority": "nse",
            "currency": "INR",
            "fiscal_year": 2024,
            "period_start": "2023-04-01",
            "period_end": "2024-03-31",
            "rows": [{"label": "Revenue from Operations", "value": "100", "scale": 1000000}],
        }
        self.assertIsNone(parse_india_results_fixture(payload, company_id=RELIANCE_ID))

    def test_fixture_parser_success(self) -> None:
        payload = {
            "data_origin": "fixture",
            "authority": "nse",
            "currency": "INR",
            "fiscal_year": 2024,
            "period_start": "2023-04-01",
            "period_end": "2024-03-31",
            "accession_or_reference": "RELIANCE-FY2024-FIXTURE",
            "rows": [
                {"label": "Revenue from Operations", "value": "900000", "scale": 1000000},
                {"label": "Net Profit", "value": "50000", "scale": 1000000},
            ],
        }
        package = parse_india_results_fixture(
            payload,
            company_id=RELIANCE_ID,
            clock=datetime(2026, 8, 8, tzinfo=UTC),
        )
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.data_origin, DataOrigin.FIXTURE)
        self.assertTrue(package.provider_name.startswith("india_fixture:"))
        assert package.income_statement is not None
        self.assertIsNotNone(package.income_statement.get(FinancialConcept.REVENUE))


class FilingPipelineTests(TestCase):
    def test_pipeline_separates_raw_facts_from_metrics(self) -> None:
        packages = build_reference_financial_packages()
        base = packages[APPLE_ID.as_text()]
        assert base.income_statement is not None
        result = assemble_package_from_facts(base, base.income_statement.facts)
        self.assertIn(FilingPipelineStage.DERIVED_METRICS, result.stages_completed)
        self.assertIn(FilingPipelineStage.PROVENANCE, result.stages_completed)
        self.assertIsNotNone(result.package)
        self.assertIsNotNone(result.metrics_result)
        self.assertGreater(len(result.raw_facts), 0)
        # Derived metrics are not raw facts.
        assert result.metrics_result is not None
        for metric in result.metrics_result.metrics:
            self.assertEqual(metric.to_dict()["kind"], "derived_metric")


class CacheFallbackHardeningTests(TestCase):
    def test_cache_hit_labels_cached_live(self) -> None:
        class LiveOnce:
            def __init__(self) -> None:
                self.calls = 0

            def get_financial_package(self, company_id, *, fiscal_year=None):
                self.calls += 1
                packages = build_reference_financial_packages()
                pkg = packages[company_id.as_text()].with_data_origin(DataOrigin.LIVE)
                return pkg

        clock = {"t": datetime(2026, 8, 8, tzinfo=UTC)}
        live = LiveOnce()
        cache = CachingFinancialDataAdapter(
            live,  # type: ignore[arg-type]
            ttl=timedelta(seconds=60),
            clock=lambda: clock["t"],
        )
        first = cache.get_financial_package(APPLE_ID)
        second = cache.get_financial_package(APPLE_ID)
        assert first is not None and second is not None
        self.assertEqual(first.data_origin, DataOrigin.LIVE)
        self.assertEqual(second.data_origin, DataOrigin.CACHED_LIVE)
        self.assertEqual(live.calls, 1)

    def test_ttl_boundary_expires(self) -> None:
        class Counting:
            def __init__(self) -> None:
                self.calls = 0

            def get_financial_package(self, company_id, *, fiscal_year=None):
                self.calls += 1
                return build_reference_financial_packages()[company_id.as_text()]

        clock = {"t": datetime(2026, 8, 8, tzinfo=UTC)}
        inner = Counting()
        cache = CachingFinancialDataAdapter(
            inner,  # type: ignore[arg-type]
            ttl=timedelta(seconds=10),
            clock=lambda: clock["t"],
        )
        cache.get_financial_package(APPLE_ID)
        clock["t"] = clock["t"] + timedelta(seconds=11)
        cache.get_financial_package(APPLE_ID)
        self.assertEqual(inner.calls, 2)

    def test_fiscal_year_key_isolation(self) -> None:
        class Counting:
            def __init__(self) -> None:
                self.calls = 0

            def get_financial_package(self, company_id, *, fiscal_year=None):
                self.calls += 1
                return InMemoryFinancialDataAdapter().get_financial_package(
                    company_id, fiscal_year=fiscal_year
                )

        inner = Counting()
        cache = CachingFinancialDataAdapter(inner, ttl=timedelta(seconds=60))  # type: ignore[arg-type]
        cache.get_financial_package(APPLE_ID, fiscal_year=2024)
        cache.get_financial_package(APPLE_ID, fiscal_year=2023)
        self.assertEqual(inner.calls, 2)

    def test_company_isolation(self) -> None:
        cache = CachingFinancialDataAdapter(
            InMemoryFinancialDataAdapter(), ttl=timedelta(seconds=60)
        )
        apple = cache.get_financial_package(APPLE_ID)
        reliance = cache.get_financial_package(RELIANCE_ID)
        assert apple is not None and reliance is not None
        self.assertNotEqual(apple.company_id, reliance.company_id)

    def test_fallback_preserves_secondary_provenance(self) -> None:
        class PrimaryDown:
            def get_financial_package(self, company_id, *, fiscal_year=None):
                raise RuntimeError("primary unavailable")

        stacked = FallbackFinancialDataAdapter(
            PrimaryDown(),  # type: ignore[arg-type]
            InMemoryFinancialDataAdapter(),
        )
        package = stacked.get_financial_package(APPLE_ID)
        assert package is not None
        self.assertEqual(package.data_origin, DataOrigin.FIXTURE)
        self.assertEqual(package.provider_name, "fixture")

    def test_both_unavailable(self) -> None:
        class Empty:
            def get_financial_package(self, company_id, *, fiscal_year=None):
                return None

        stacked = FallbackFinancialDataAdapter(Empty(), Empty())  # type: ignore[arg-type]
        self.assertIsNone(stacked.get_financial_package(APPLE_ID))

    def test_cache_concurrency(self) -> None:
        adapter = CachingFinancialDataAdapter(
            InMemoryFinancialDataAdapter(), ttl=timedelta(seconds=60)
        )
        errors: list[BaseException] = []

        def worker() -> None:
            try:
                for _ in range(20):
                    adapter.get_financial_package(APPLE_ID)
            except BaseException as exc:
                errors.append(exc)

        threads = [Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
