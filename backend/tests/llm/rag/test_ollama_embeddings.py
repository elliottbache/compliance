from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from compliance.llm.rag.ollama_embeddings import (
    OllamaEmbeddingProvider,
    OllamaEmbeddingResponseError,
)


def _settings(*, model: str | None = "embed-test") -> SimpleNamespace:
    return SimpleNamespace(
        rag_embedding_model=model,
        ollama_base_url="http://ollama.test:11434",
        ollama_timeout_seconds=123,
    )


class TestOllamaEmbeddingProvider:
    def test_uses_configured_client_model_and_input(self) -> None:
        client = MagicMock()
        client.embed.return_value = SimpleNamespace(embeddings=[[1, 2.5, -3]])

        with (
            patch(
                "compliance.llm.rag.ollama_embeddings.settings",
                _settings(),
            ),
            patch(
                "compliance.llm.rag.ollama_embeddings.ollama.Client",
                return_value=client,
            ) as client_factory,
        ):
            provider = OllamaEmbeddingProvider()
            result = provider.embed_text("embedding input")

        assert result == [1.0, 2.5, -3.0]
        client_factory.assert_called_once_with(
            host="http://ollama.test:11434",
            timeout=123,
        )
        client.embed.assert_called_once_with(
            model="embed-test",
            input="embedding input",
        )

    def test_explicit_model_overrides_configuration(self) -> None:
        with patch(
            "compliance.llm.rag.ollama_embeddings.settings",
            _settings(model="configured-model"),
        ):
            provider = OllamaEmbeddingProvider(model=" override-model ")

        assert provider.model == "override-model"

    def test_requires_embedding_model(self) -> None:
        with (
            patch(
                "compliance.llm.rag.ollama_embeddings.settings",
                _settings(model=None),
            ),
            pytest.raises(RuntimeError, match="RAG_EMBEDDING_MODEL is required"),
        ):
            OllamaEmbeddingProvider()

    def test_rejects_empty_input_without_calling_ollama(self) -> None:
        client = MagicMock()
        with (
            patch(
                "compliance.llm.rag.ollama_embeddings.settings",
                _settings(),
            ),
            patch(
                "compliance.llm.rag.ollama_embeddings.ollama.Client",
                return_value=client,
            ),
            pytest.raises(ValueError, match="input cannot be empty"),
        ):
            OllamaEmbeddingProvider().embed_text("  ")

        client.embed.assert_not_called()

    @pytest.mark.parametrize(
        "embeddings",
        [
            [],
            [[]],
            [[1.0], [2.0]],
            [[float("nan")]],
            [[float("inf")]],
            [[True]],
            [["not-a-number"]],
        ],
    )
    def test_rejects_invalid_embedding_response(self, embeddings) -> None:
        client = MagicMock()
        client.embed.return_value = SimpleNamespace(embeddings=embeddings)

        with (
            patch(
                "compliance.llm.rag.ollama_embeddings.settings",
                _settings(),
            ),
            patch(
                "compliance.llm.rag.ollama_embeddings.ollama.Client",
                return_value=client,
            ),
            pytest.raises(OllamaEmbeddingResponseError),
        ):
            OllamaEmbeddingProvider().embed_text("embedding input")
