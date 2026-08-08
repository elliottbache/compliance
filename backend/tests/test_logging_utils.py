import io
import json
import logging
from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest
from compliance.logging_utils import (
    JsonLogFormatter,
    RedactingTextFormatter,
    _default_log_dir,
    _set_formatter,
    configure_logging,
    redact_sensitive_text,
)


class TestConfigureLogging:
    def test_raises_for_invalid_level(self) -> None:
        with pytest.raises(ValueError, match="Invalid log level"):
            configure_logging(level="not-a-level")

    def test_configures_root_handlers_for_non_tutorial(self, tmp_path) -> None:
        root = logging.getLogger()
        original_handlers = list(root.handlers)

        try:
            old_handler = MagicMock(spec=logging.Handler)
            root.addHandler(old_handler)

            with patch("compliance.logging_utils._default_log_dir") as mock_log_dir:
                mock_log_dir.return_value = tmp_path / "logs"
                with patch(
                    "compliance.logging_utils.RotatingFileHandler"
                ) as mock_rotating:
                    rotating_handler = MagicMock(spec=logging.Handler)
                    mock_rotating.return_value = rotating_handler

                    configure_logging(level="DEBUG", is_tutorial=False)

            assert root.level == logging.DEBUG
            assert old_handler.close.called
            assert len(root.handlers) == 2
            assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
            assert rotating_handler in root.handlers
            mock_rotating.assert_called_once_with(
                filename=tmp_path / "logs/compliance.log",
                mode="a",
                maxBytes=50 * 1024 * 1024,
                backupCount=2,
            )
        finally:
            for handler in list(root.handlers):
                root.removeHandler(handler)
                with suppress(Exception):
                    handler.close()
            for handler in original_handlers:
                root.addHandler(handler)

    def test_uses_file_handler_in_tutorial_mode(self, tmp_path) -> None:
        root = logging.getLogger()
        original_handlers = list(root.handlers)

        try:
            with patch("compliance.logging_utils._default_log_dir") as mock_log_dir:
                mock_log_dir.return_value = tmp_path / "logs"
                with patch("logging.FileHandler") as mock_file_handler:
                    file_handler = MagicMock(spec=logging.Handler)
                    mock_file_handler.return_value = file_handler

                    configure_logging(level="INFO", is_tutorial=True)

            mock_file_handler.assert_called_once_with(
                filename=tmp_path / "logs/compliance.log",
                mode="w",
            )
            assert file_handler in root.handlers
        finally:
            for handler in list(root.handlers):
                root.removeHandler(handler)
                with suppress(Exception):
                    handler.close()
            for handler in original_handlers:
                root.addHandler(handler)

    def test_routes_python_warnings_through_root_logger(self, tmp_path) -> None:
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        warn_logger = logging.getLogger("py.warnings")
        original_warn_handlers = list(warn_logger.handlers)
        original_warn_propagate = warn_logger.propagate

        try:
            with patch("compliance.logging_utils._default_log_dir") as mock_log_dir:
                mock_log_dir.return_value = tmp_path / "logs"
                with patch(
                    "compliance.logging_utils.RotatingFileHandler"
                ) as mock_rotating:
                    mock_rotating.return_value = MagicMock(spec=logging.Handler)

                    configure_logging(level="INFO", is_tutorial=False)

            assert warn_logger.handlers == []
            assert warn_logger.propagate is True
        finally:
            for handler in list(root.handlers):
                root.removeHandler(handler)
                with suppress(Exception):
                    handler.close()
            for handler in original_handlers:
                root.addHandler(handler)

            warn_logger.handlers.clear()
            for handler in original_warn_handlers:
                warn_logger.addHandler(handler)
            warn_logger.propagate = original_warn_propagate

    def test_configures_json_formatters_when_structured(self, tmp_path) -> None:
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        try:
            with patch("compliance.logging_utils._default_log_dir") as mock_log_dir:
                mock_log_dir.return_value = log_dir

                configure_logging(level="INFO", structured=True)

            assert len(root.handlers) == 2
            assert all(
                isinstance(handler.formatter, JsonLogFormatter)
                for handler in root.handlers
            )
        finally:
            for handler in list(root.handlers):
                root.removeHandler(handler)
                with suppress(Exception):
                    handler.close()
            for handler in original_handlers:
                root.addHandler(handler)


class TestSetFormatter:
    def test_sets_deterministic_format_in_tutorial_mode(self) -> None:
        handler = logging.StreamHandler()

        _set_formatter(handler, is_tutorial=True)

        assert handler.formatter._style._fmt == (
            "2000-01-01T00:00:00+0100 {levelname} {name}: {message}"
        )

    def test_sets_asctime_format_in_non_tutorial_mode(self) -> None:
        handler = logging.StreamHandler()

        _set_formatter(handler, is_tutorial=False)

        assert (
            handler.formatter._style._fmt == "{asctime} {levelname} {name}: {message}"
        )

    def test_sets_redacting_text_formatter_for_text_logs(self) -> None:
        handler = logging.StreamHandler()

        _set_formatter(handler)

        assert isinstance(handler.formatter, RedactingTextFormatter)

    def test_sets_json_formatter_for_structured_logs(self) -> None:
        handler = logging.StreamHandler()

        _set_formatter(handler, structured=True)

        assert isinstance(handler.formatter, JsonLogFormatter)


class TestJsonLogFormatter:
    def test_formats_record_as_json(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("compliance.test.json")
        original_handlers = list(logger.handlers)
        original_level = logger.level
        original_propagate = logger.propagate

        try:
            logger.handlers.clear()
            logger.setLevel(logging.INFO)
            logger.propagate = False
            handler.setFormatter(JsonLogFormatter(is_tutorial=True))
            logger.addHandler(handler)

            logger.info("structured message")

            payload = json.loads(stream.getvalue())

            assert payload["timestamp"] == "2000-01-01T00:00:00+01:00"
            assert payload["level"] == "INFO"
            assert payload["logger"] == "compliance.test.json"
            assert payload["message"] == "structured message"
            assert payload["module"] == "test_logging_utils"
            assert payload["function"] == "test_formats_record_as_json"
            assert isinstance(payload["line"], int)
        finally:
            logger.handlers.clear()
            for original_handler in original_handlers:
                logger.addHandler(original_handler)
            logger.setLevel(original_level)
            logger.propagate = original_propagate

    def test_redacts_sensitive_message_values(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("compliance.test.redaction")
        original_handlers = list(logger.handlers)
        original_level = logger.level
        original_propagate = logger.propagate

        try:
            logger.handlers.clear()
            logger.setLevel(logging.INFO)
            logger.propagate = False
            handler.setFormatter(JsonLogFormatter(is_tutorial=True))
            logger.addHandler(handler)

            logger.info(
                "password=plain token=abc api_key=key secret=value "
                "Authorization: Bearer jwt-token"
            )

            payload = json.loads(stream.getvalue())

            assert "plain" not in payload["message"]
            assert "abc" not in payload["message"]
            assert "value" not in payload["message"]
            assert "jwt-token" not in payload["message"]
            assert "[redacted]" in payload["message"]
        finally:
            logger.handlers.clear()
            for original_handler in original_handlers:
                logger.addHandler(original_handler)
            logger.setLevel(original_level)
            logger.propagate = original_propagate

    def test_includes_safe_extra_context(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("compliance.test.context")
        original_handlers = list(logger.handlers)
        original_level = logger.level
        original_propagate = logger.propagate

        try:
            logger.handlers.clear()
            logger.setLevel(logging.INFO)
            logger.propagate = False
            handler.setFormatter(JsonLogFormatter(is_tutorial=True))
            logger.addHandler(handler)

            logger.info(
                "upload failed",
                extra={
                    "event": "attachment_upload_failed",
                    "attachment_id": 50,
                    "token": "secret-token",
                },
            )

            payload = json.loads(stream.getvalue())

            assert payload["context"] == {
                "event": "attachment_upload_failed",
                "attachment_id": 50,
                "token": "[redacted]",
            }
        finally:
            logger.handlers.clear()
            for original_handler in original_handlers:
                logger.addHandler(original_handler)
            logger.setLevel(original_level)
            logger.propagate = original_propagate

    def test_formats_exception_details(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("compliance.test.exception")
        original_handlers = list(logger.handlers)
        original_level = logger.level
        original_propagate = logger.propagate

        try:
            logger.handlers.clear()
            logger.setLevel(logging.ERROR)
            logger.propagate = False
            handler.setFormatter(JsonLogFormatter(is_tutorial=True))
            logger.addHandler(handler)

            try:
                raise RuntimeError("broken")
            except RuntimeError:
                logger.exception("failed operation")

            payload = json.loads(stream.getvalue())

            assert payload["message"] == "failed operation"
            assert payload["exception"]["type"] == "RuntimeError"
            assert payload["exception"]["message"] == "broken"
            assert "RuntimeError: broken" in payload["exception"]["traceback"]
        finally:
            logger.handlers.clear()
            for original_handler in original_handlers:
                logger.addHandler(original_handler)
            logger.setLevel(original_level)
            logger.propagate = original_propagate


class TestRedactSensitiveText:
    def test_redacts_password_token_secret_api_key_and_bearer_values(self) -> None:
        result = redact_sensitive_text(
            "password=plain token: abc secret=value api_key=key Bearer jwt-token"
        )

        assert "plain" not in result
        assert "abc" not in result
        assert "value" not in result
        assert "jwt-token" not in result
        assert "password=[redacted]" in result
        assert "token: [redacted]" in result
        assert "secret=[redacted]" in result
        assert "api_key=[redacted]" in result
        assert "Bearer [redacted]" in result


class TestDefaultLogDir:
    def test_uses_xdg_state_home_on_non_windows(self, tmp_path) -> None:
        fake_base = MagicMock()
        fake_compliance = MagicMock()
        fake_logs = MagicMock()

        fake_base.__truediv__.return_value = fake_compliance
        fake_compliance.__truediv__.return_value = fake_logs

        with (
            patch("compliance.logging_utils.os.name", "posix"),
            patch(
                "compliance.logging_utils.os.getenv",
                return_value=tmp_path / "state",
            ),
            patch(
                "compliance.logging_utils.pathlib.Path",
                return_value=fake_base,
            ) as mock_path,
        ):
            result = _default_log_dir()

        mock_path.assert_called_once_with(tmp_path / "state")
        fake_logs.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        assert result == fake_logs

    def test_uses_localappdata_on_windows(self, tmp_path) -> None:
        fake_base = MagicMock()
        fake_compliance = MagicMock()
        fake_logs = MagicMock()

        fake_base.__truediv__.return_value = fake_compliance
        fake_compliance.__truediv__.return_value = fake_logs

        with (
            patch("compliance.logging_utils.os.name", "nt"),
            patch(
                "compliance.logging_utils.os.getenv",
                return_value=tmp_path / "AppData/Local",
            ),
            patch(
                "compliance.logging_utils.pathlib.Path",
                return_value=fake_base,
            ) as mock_path,
        ):
            result = _default_log_dir()

        mock_path.assert_called_once_with(tmp_path / "AppData/Local")
        fake_logs.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        assert result == fake_logs
