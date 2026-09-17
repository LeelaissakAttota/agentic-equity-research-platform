"""F06 regression: Docker Compose must never publish a host port on all
interfaces by omission (see F06_DOCKER_COMPOSE_EXPOSURE_REMEDIATION_PLAN.md).

Docker's default host-bind address when a `ports:` entry omits a host IP is
"all interfaces" (0.0.0.0 / ::). This was reproduced against the live
container (`docker inspect` showed HostIp "0.0.0.0" and "::", and the service
answered unauthenticated requests on the host's LAN interface) before the
fix. These tests validate the parsed Compose structure directly rather than
grepping for a literal string, so they hold for any service/port entry added
in the future (e.g. if PostgreSQL/Redis are introduced per DEPLOYMENT_PLAN.md).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from unittest import TestCase

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# Docker's own wildcard/all-interfaces spellings. A missing host_ip is treated
# as wildcard too, since that is exactly what Docker defaults to.
_WILDCARD_HOST_IPS = frozenset({"", "0.0.0.0", "::", "[::]"})

_ENV_VAR_PATTERN = re.compile(r"\$\{[^}]*\}")
_PROTOCOL_SUFFIX_PATTERN = re.compile(r"/(tcp|udp)$", re.IGNORECASE)


def _load_compose() -> dict[str, Any]:
    with COMPOSE_FILE.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise AssertionError("docker-compose.yml did not parse to a mapping")
    return loaded


def _tokenize_short_syntax(spec: str) -> list[str]:
    """Split a short-syntax port string on ':', treating ${...} as atomic.

    Compose's ${VAR:-default} interpolation syntax contains a literal ':',
    which would otherwise be misinterpreted as a host/port separator.
    """

    placeholders: dict[str, str] = {}

    def _mask(match: re.Match[str]) -> str:
        key = f"@@ENV{len(placeholders)}@@"
        placeholders[key] = match.group(0)
        return key

    masked = _ENV_VAR_PATTERN.sub(_mask, spec)
    return [placeholders.get(token, token) for token in masked.split(":")]


def _host_ip_for_entry(entry: Any) -> str:
    """Return the entry's effective host IP, or "" when none is specified.

    An empty string signals "unrestricted" (Docker's all-interfaces default),
    matching how an absent host IP behaves in practice.
    """

    if isinstance(entry, dict):
        # Long syntax: {mode, target, published, protocol, host_ip?}.
        return str(entry.get("host_ip") or "")

    if isinstance(entry, int):
        # Bare container-port publish (e.g. `8000`): ephemeral host port,
        # still unrestricted by default.
        return ""

    if isinstance(entry, str):
        spec = _PROTOCOL_SUFFIX_PATTERN.sub("", entry)
        tokens = _tokenize_short_syntax(spec)
        if len(tokens) == 3:
            # host_ip:host_port:container_port
            return tokens[0]
        if len(tokens) in (1, 2):
            # host_port:container_port, or a bare container_port -- no host
            # IP was specified, so Docker publishes on all interfaces.
            return ""
        raise AssertionError(f"unrecognized Compose short-syntax port spec: {entry!r}")

    raise AssertionError(f"unrecognized Compose port entry type: {entry!r}")


class DockerComposePortBindingTests(TestCase):
    """Every published host port must bind to an explicit, non-wildcard IP."""

    def test_compose_file_exists(self) -> None:
        self.assertTrue(COMPOSE_FILE.is_file(), f"expected {COMPOSE_FILE} to exist")

    def test_every_published_port_has_explicit_non_wildcard_host_ip(self) -> None:
        compose = _load_compose()
        services = compose.get("services")
        assert isinstance(services, dict) and services, "expected at least one service"

        checked_any_port = False
        for service_name, service_def in services.items():
            if not isinstance(service_def, dict):
                continue
            port_entries = service_def.get("ports")
            if not port_entries:
                continue
            for entry in port_entries:
                checked_any_port = True
                host_ip = _host_ip_for_entry(entry)
                self.assertNotIn(
                    host_ip,
                    _WILDCARD_HOST_IPS,
                    f"service {service_name!r} publishes {entry!r} without an explicit, "
                    "non-wildcard host IP -- Docker would bind this to all interfaces",
                )

        # This suite exists specifically to police published ports; if the
        # compose file stops publishing any, that's a meaningful change this
        # test should surface rather than silently pass with zero coverage.
        self.assertTrue(checked_any_port, "expected at least one published port to check")

    def test_api_service_is_bound_to_loopback(self) -> None:
        compose = _load_compose()
        api_ports = compose["services"]["api"]["ports"]
        self.assertEqual(len(api_ports), 1)
        self.assertEqual(_host_ip_for_entry(api_ports[0]), "127.0.0.1")


class DockerComposeConfigValidityTests(TestCase):
    """Optional live validation via the Docker CLI, skipped when unavailable."""

    def test_docker_compose_config_succeeds(self) -> None:
        if shutil.which("docker") is None:
            self.skipTest("docker CLI not available in this environment")
        try:
            result = subprocess.run(
                ["docker", "compose", "config", "--quiet"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.skipTest(f"docker compose unavailable/unresponsive: {exc}")
        if result.returncode != 0 and "Cannot connect" in (result.stderr or ""):
            self.skipTest("Docker engine not running in this environment")
        self.assertEqual(
            result.returncode,
            0,
            f"docker compose config failed: {result.stderr}",
        )
