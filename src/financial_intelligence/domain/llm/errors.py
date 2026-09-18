"""Provider-agnostic failure classification for LLM model calls.

Mirrors the normalization style of ``infrastructure/http/bounded_client.py``'s
``HttpFailureKind`` so LLM call outcomes stay typed and comparable across
providers, without naming any specific provider or transport.
"""

from __future__ import annotations

from enum import StrEnum


class ModelFailureKind(StrEnum):
    """Normalized LLM model-call failure categories."""

    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_ERROR = "authentication_error"
    INVALID_REQUEST = "invalid_request"
    CONTEXT_EXCEEDED = "context_exceeded"
    CONTENT_POLICY = "content_policy"
    MALFORMED_OUTPUT = "malformed_output"
    UPSTREAM_ERROR = "upstream_error"
    NETWORK_ERROR = "network_error"
    POLICY_VIOLATION = "policy_violation"
    UNKNOWN = "unknown"
