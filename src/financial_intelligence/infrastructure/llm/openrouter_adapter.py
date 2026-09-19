"""Live LlmRouterPort adapter calling OpenRouter's chat-completions API.

Uses only ``BoundedHttpClient.post_json`` (infrastructure/http) for network
I/O — no direct urllib/socket calls, no other HTTP library. Automated tests
must inject a fake transport at that boundary; CI never depends on a live
OpenRouter call. The API key never appears in a log line or an exception
message raised by this module.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from pydantic import SecretStr

from financial_intelligence.domain.llm import (
    ModelCallStatus,
    ModelFailureKind,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)
from financial_intelligence.infrastructure.http import (
    BoundedHttpClient,
    HttpFailureKind,
    HttpTransportError,
)
from financial_intelligence.observability.logging import get_logger

logger = get_logger("financial_intelligence.infrastructure.llm.openrouter_adapter")

_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterAdapter:
    """Live LlmRouterPort implementation targeting OpenRouter's free-model catalog.

    The configured model comes entirely from settings (``primary_free_model``);
    this adapter never hardcodes a model name and never selects a different
    (for example, paid) model on failure.
    """

    provider_name = "openrouter"

    def __init__(
        self,
        http: BoundedHttpClient,
        *,
        api_key: SecretStr,
        model: str,
        max_output_tokens_ceiling: int,
    ) -> None:
        if not model.strip():
            msg = "model is required"
            raise ValueError(msg)
        if max_output_tokens_ceiling < 1:
            msg = "max_output_tokens_ceiling must be positive"
            raise ValueError(msg)
        self._http = http
        self._api_key = api_key
        self._model = model.strip()
        self._max_output_tokens_ceiling = max_output_tokens_ceiling

    def complete(self, request: ModelRequest) -> ModelResponse:
        if request.max_output_tokens > self._max_output_tokens_ceiling:
            logger.info(
                "openrouter_request_exceeds_configured_output_ceiling",
                extra={
                    "call_id": request.call_id.as_text(),
                    "model": self._model,
                    "requested_max_output_tokens": request.max_output_tokens,
                    "configured_ceiling": self._max_output_tokens_ceiling,
                },
            )
            return self._failed(request, ModelFailureKind.INVALID_REQUEST)

        payload: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "max_tokens": request.max_output_tokens,
        }
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}

        try:
            body = self._http.post_json(_CHAT_COMPLETIONS_URL, payload, extra_headers=headers)
        except HttpTransportError as exc:
            failure_kind = self._map_transport_failure(exc)
            logger.info(
                "openrouter_call_failed",
                extra={
                    "call_id": request.call_id.as_text(),
                    "model": self._model,
                    "failure_kind": failure_kind.value,
                    "status_code": exc.status_code,
                    "correlation_id": request.correlation_id,
                },
            )
            return self._failed(request, failure_kind)

        try:
            return self._map_success(request, body)
        except (TypeError, ValueError, KeyError):
            logger.info(
                "openrouter_malformed_response",
                extra={
                    "call_id": request.call_id.as_text(),
                    "model": self._model,
                    "correlation_id": request.correlation_id,
                },
            )
            return self._failed(request, ModelFailureKind.MALFORMED_OUTPUT)

    def _map_success(self, request: ModelRequest, body: dict[str, object]) -> ModelResponse:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            msg = "missing choices"
            raise ValueError(msg)
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            msg = "invalid choice entry"
            raise ValueError(msg)
        message = first_choice.get("message")
        if not isinstance(message, dict):
            msg = "invalid message entry"
            raise ValueError(msg)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            msg = "missing or empty content"
            raise ValueError(msg)

        model_used_raw = body.get("model")
        model_used = (
            model_used_raw
            if isinstance(model_used_raw, str) and model_used_raw.strip()
            else self._model
        )

        usage = self._map_usage(body.get("usage"))
        # $0 cost policy: require explicitly known finite zero cost.
        # Missing, malformed, non-finite, or positive cost → POLICY_VIOLATION.
        if not usage.cost_known or usage.estimated_cost > 0:
            logger.error(
                "openrouter_nonzero_cost_policy_violation",
                extra={"call_id": request.call_id.as_text(), "model": model_used},
            )
            return self._failed(request, ModelFailureKind.POLICY_VIOLATION)

        return ModelResponse(
            call_id=request.call_id,
            status=ModelCallStatus.SUCCEEDED,
            model_used=model_used,
            content=content,
            usage=usage,
            retry_count=0,
        )

    @staticmethod
    def _map_usage(raw: object) -> ModelUsage:
        if not isinstance(raw, dict):
            return ModelUsage()
        input_tokens = raw.get("prompt_tokens")
        output_tokens = raw.get("completion_tokens")
        cost_raw = raw.get("cost")
        if cost_raw is None:
            # Missing cost — not known, fail closed at policy boundary
            return ModelUsage(
                input_tokens=(
                    input_tokens if isinstance(input_tokens, int) and input_tokens >= 0 else None
                ),
                output_tokens=(
                    output_tokens if isinstance(output_tokens, int) and output_tokens >= 0 else None
                ),
                estimated_cost=Decimal("0"),
                cost_known=False,
            )
        if not isinstance(cost_raw, (int, float, str)):
            # Malformed cost type — not known, fail closed
            return ModelUsage(
                input_tokens=(
                    input_tokens if isinstance(input_tokens, int) and input_tokens >= 0 else None
                ),
                output_tokens=(
                    output_tokens if isinstance(output_tokens, int) and output_tokens >= 0 else None
                ),
                estimated_cost=Decimal("0"),
                cost_known=False,
            )
        try:
            cost = Decimal(str(cost_raw))
        except InvalidOperation:
            # Unparseable cost — not known, fail closed
            return ModelUsage(
                input_tokens=(
                    input_tokens if isinstance(input_tokens, int) and input_tokens >= 0 else None
                ),
                output_tokens=(
                    output_tokens if isinstance(output_tokens, int) and output_tokens >= 0 else None
                ),
                estimated_cost=Decimal("0"),
                cost_known=False,
            )
        if not cost.is_finite():
            # NaN or Infinity — not known, fail closed
            return ModelUsage(
                input_tokens=(
                    input_tokens if isinstance(input_tokens, int) and input_tokens >= 0 else None
                ),
                output_tokens=(
                    output_tokens if isinstance(output_tokens, int) and output_tokens >= 0 else None
                ),
                estimated_cost=Decimal("0"),
                cost_known=False,
            )
        # Explicit finite cost (zero or positive) — known
        return ModelUsage(
            input_tokens=(
                input_tokens if isinstance(input_tokens, int) and input_tokens >= 0 else None
            ),
            output_tokens=(
                output_tokens if isinstance(output_tokens, int) and output_tokens >= 0 else None
            ),
            estimated_cost=cost,
            cost_known=True,
        )

    @staticmethod
    def _failed(request: ModelRequest, failure_kind: ModelFailureKind) -> ModelResponse:
        return ModelResponse(
            call_id=request.call_id,
            status=ModelCallStatus.FAILED,
            model_used=None,
            content=None,
            usage=ModelUsage(),
            retry_count=0,
            failure_kind=failure_kind,
        )

    @staticmethod
    def _map_transport_failure(exc: HttpTransportError) -> ModelFailureKind:
        if exc.kind is HttpFailureKind.TIMEOUT:
            return ModelFailureKind.TIMEOUT
        if exc.kind is HttpFailureKind.NETWORK_ERROR:
            return ModelFailureKind.NETWORK_ERROR
        if exc.kind is HttpFailureKind.UNAUTHORIZED:
            return ModelFailureKind.AUTHENTICATION_ERROR
        if exc.kind is HttpFailureKind.RATE_LIMITED:
            return ModelFailureKind.RATE_LIMITED
        if exc.kind is HttpFailureKind.UPSTREAM_ERROR:
            return ModelFailureKind.UPSTREAM_ERROR
        if exc.kind is HttpFailureKind.OVERSIZED:
            return ModelFailureKind.UPSTREAM_ERROR
        if exc.kind is HttpFailureKind.NOT_FOUND:
            return ModelFailureKind.INVALID_REQUEST
        if exc.kind is HttpFailureKind.INVALID_RESPONSE:
            # A 200 status with an unparsable body is a malformed response;
            # any other status here reflects a rejected request (see
            # BoundedHttpClient._classify_status for the underlying mapping).
            if exc.status_code == 200:
                return ModelFailureKind.MALFORMED_OUTPUT
            return ModelFailureKind.INVALID_REQUEST
        return ModelFailureKind.UNKNOWN
