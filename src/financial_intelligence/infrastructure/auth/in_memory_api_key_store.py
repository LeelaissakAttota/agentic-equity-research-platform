"""In-memory API-key store (Phase 11.2 foundation).

This adapter stores API keys in process memory using constant-time comparison.
It is the Phase 11.2 implementation of ``ApiKeyStorePort``.

LIMITATIONS (documented intentionally):
- Keys live only in the running process; restart clears all keys.
- Keys come from application configuration, not a database.
- Persistent key storage (create/revoke/rotate via API) belongs to a later
  persistence phase when PostgreSQL adapters are introduced.
- Only one set of keys is active per process launch.
"""

from __future__ import annotations

import secrets


class InMemoryApiKeyStore:
    """Validate inbound API keys against a process-local configured set.

    Uses ``secrets.compare_digest`` for every comparison to ensure
    constant-time behaviour regardless of key length or content.
    Empty credentials are rejected before comparison.
    """

    def __init__(self, raw_keys: frozenset[str]) -> None:
        """Construct the store from an already-parsed set of non-empty keys.

        The caller is responsible for stripping, deduplicating, and filtering
        empty strings before constructing this instance.
        """
        if not isinstance(raw_keys, frozenset):
            msg = "raw_keys must be a frozenset"
            raise TypeError(msg)
        self._keys: frozenset[str] = raw_keys

    @classmethod
    def from_csv(cls, csv_value: str) -> InMemoryApiKeyStore:
        """Build from a comma-separated API-key string (e.g. from settings).

        Empty tokens and whitespace-only tokens are silently dropped.
        The resulting store may contain zero keys if the input is blank or
        contains only empty tokens; in that state ``is_valid`` always returns
        ``False``.
        """
        keys = frozenset(token for raw in csv_value.split(",") if (token := raw.strip()))
        return cls(keys)

    def is_valid(self, presented_key: str) -> bool:
        """Return True only if ``presented_key`` matches a configured key.

        Uses ``secrets.compare_digest`` for every comparison.
        Returns False immediately (without comparing) if the presented key or
        the store is empty, to avoid leaking information about store contents.
        """
        if not presented_key or not self._keys:
            return False
        return any(secrets.compare_digest(presented_key, stored) for stored in self._keys)

    @property
    def has_keys(self) -> bool:
        """Return True when at least one key is configured."""
        return bool(self._keys)
