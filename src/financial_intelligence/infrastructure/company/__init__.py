"""Company catalog infrastructure adapters."""

from financial_intelligence.infrastructure.company.in_memory_catalog import InMemoryCompanyCatalog
from financial_intelligence.infrastructure.company.reference_dataset import (
    build_reference_companies,
)

__all__ = ["InMemoryCompanyCatalog", "build_reference_companies"]
