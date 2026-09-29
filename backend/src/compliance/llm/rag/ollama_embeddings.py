"""Ollama provider for RAG clause embeddings."""

import logging
import math

import httpx
import ollama
from compliance.config import settings
from compliance.llm.ollama_retry import stop_after_ollama_attempts
from tenacity import retry, retry_if_exception_type, wait_exponential

logger = logging.getLogger(__name__)


class OllamaEmbeddingResponseError(RuntimeError):
    """Raised when Ollama returns an unusable embedding response."""


class OllamaEmbeddingProvider:
    """Generate validated embedding vectors with Ollama."""

    def __init__(self, model: str | None = None) -> None:
        resolved_model = model or settings.rag_embedding_model
        if not resolved_model or not resolved_model.strip():
            raise RuntimeError(
                "RAG_EMBEDDING_MODEL is required to generate embeddings."
            )
        self.model = resolved_model.strip()

    @retry(
        stop=stop_after_ollama_attempts,
        wait=wait_exponential(multiplier=1, min=2, max=32),
        retry=retry_if_exception_type(
            (ollama.ResponseError, httpx.TransportError, ConnectionRefusedError)
        ),
        reraise=True,
    )
    def embed_text(self, text: str) -> list[float]:
        """Send one non-empty input to Ollama and return its validated vector."""
        if not text.strip():
            raise ValueError("Ollama embedding input cannot be empty.")

        client = ollama.Client(
            host=settings.ollama_base_url,
            timeout=settings.ollama_timeout_seconds,
        )

        try:
            response = client.embed(model=self.model, input=text)
        except ollama.ResponseError:
            logger.exception("Ollama returned an embedding response error.")
            raise
        except httpx.ReadTimeout:
            logger.exception(
                "Timed out waiting for Ollama embeddings at %s.",
                settings.ollama_base_url,
            )
            raise
        except (httpx.TransportError, ConnectionRefusedError):
            logger.exception(
                "Could not connect to Ollama embeddings at %s.",
                settings.ollama_base_url,
            )
            raise

        if len(response.embeddings) != 1 or not response.embeddings[0]:
            raise OllamaEmbeddingResponseError(
                "Ollama must return exactly one non-empty embedding vector."
            )

        vector = []
        for value in response.embeddings[0]:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise OllamaEmbeddingResponseError(
                    "Ollama embedding vector must contain only finite numbers."
                )
            vector.append(float(value))

        return vector
