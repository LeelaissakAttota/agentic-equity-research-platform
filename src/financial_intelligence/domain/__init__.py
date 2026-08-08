"""Provider-neutral domain primitives.

Domain code must remain free of FastAPI, providers, and infrastructure SDKs.
"""

from financial_intelligence.domain.research_run import ResearchRunId

__all__ = ["ResearchRunId"]
