# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY pyproject.toml README.md LICENSE requirements-lock.txt ./
COPY src ./src

# requirements-lock.txt is a flat `pip freeze` of the verified dev venv (no
# platform markers), so it is used as a pip *constraints* file rather than a
# requirements file: any package pip resolves that also appears in the lock
# is forced to that exact pinned version (closing F07's drift), while
# platform-conditional packages the lock cannot represent for this Linux
# image (e.g. uvloop, pulled in only here by uvicorn[standard]) still resolve
# normally instead of silently disappearing.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -c requirements-lock.txt .

FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    ALLOWED_HOSTS="localhost,127.0.0.1" \
    API_MAX_REQUEST_BODY_BYTES=1048576 \
    ALLOW_PAID_MODELS=false

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser pyproject.toml README.md LICENSE ./

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "financial_intelligence.main:app", "--host", "0.0.0.0", "--port", "8000"]
