"""Shared retry policy for Ollama API calls."""

import httpx
import ollama
from tenacity import RetryCallState


def stop_after_ollama_attempts(retry_state: RetryCallState) -> bool:
    """Stop retries according to the Ollama or transport failure type."""
    if retry_state.outcome is None:
        return retry_state.attempt_number >= 2

    exc = retry_state.outcome.exception()
    if isinstance(exc, (httpx.TransportError, ConnectionRefusedError)):
        return retry_state.attempt_number >= 6

    if not isinstance(exc, ollama.ResponseError):
        return retry_state.attempt_number >= 1

    status_code = exc.status_code or 0

    if status_code in {408, 429} or status_code >= 500:
        return retry_state.attempt_number >= 6

    if status_code in {400, 401, 402, 403, 404, 413, 422}:
        return retry_state.attempt_number >= 1

    if status_code == 409:
        return retry_state.attempt_number >= 2

    return retry_state.attempt_number >= 1
