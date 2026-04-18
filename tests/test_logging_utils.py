import logging
from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest

from compliance.logging_utils import (
    _default_log_dir,
    _set_formatter,
    configure_logging,
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
