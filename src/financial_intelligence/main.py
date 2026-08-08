"""ASGI entrypoint for local and container launches."""

from financial_intelligence.api import create_app

app = create_app()
