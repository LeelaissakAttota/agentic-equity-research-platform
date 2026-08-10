"""Backward-compatible REST API version policy and OpenAPI metadata."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

CURRENT_API_VERSION = "v1"
VERSIONED_API_PREFIX = f"/{CURRENT_API_VERSION}"
LEGACY_API_STATUS = "supported"


def install_openapi_version_policy(app: FastAPI) -> None:
    """Expose the frozen API version policy without changing package version metadata."""

    original_openapi: Callable[[], dict[str, Any]] = app.openapi

    def versioned_openapi() -> dict[str, Any]:
        schema = original_openapi()
        info = schema.setdefault("info", {})
        info["x-api-version"] = CURRENT_API_VERSION
        schema["x-api-versioning"] = {
            "current": CURRENT_API_VERSION,
            "strategy": "major_path_prefix",
            "versioned_prefix": VERSIONED_API_PREFIX,
            "legacy_unversioned_status": LEGACY_API_STATUS,
            "breaking_changes": "new_major_prefix_required",
            "deprecation": "owner_approval_and_one_released_window",
        }
        return schema

    # FastAPI documents replacing ``app.openapi`` as its schema-extension hook.
    app.openapi = versioned_openapi  # type: ignore[method-assign]
