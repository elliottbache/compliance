"""Logging helpers.

This module configures the **root** logger so application code can simply call
``logging.getLogger(__name__)`` and emit messages.

Behavior:

- A file handler is attached at the requested level (default: ``INFO``) and
  writes to an OS-appropriate directory (``XDG_STATE_HOME`` on Linux/WSL or
  ``LOCALAPPDATA`` on Windows).
- A stderr handler is attached at ``WARNING`` and above.
- Python warnings are routed through logging (via ``logging.captureWarnings``).

In tutorial mode (``is_tutorial=True``), log timestamps are made deterministic so
test outputs and tutorial logs are reproducible.
"""

import logging
import os
import pathlib
import sys
from logging.handlers import RotatingFileHandler


def configure_logging(*, level: str = "INFO", is_tutorial: bool = False) -> None:
    """Configure root logging for the application.

    This attaches two handlers to the **root** logger.

    The file handler writes at ``level`` to
    ``<state-dir>/compliance/logs/compliance.log``. On Linux/WSL, the state
    directory is ``$XDG_STATE_HOME`` with a fallback to ``~/.local/state``. On
    Windows, it is ``%LOCALAPPDATA%`` with a fallback to ``~/AppData/Local``.
    The file handler rotates in non-tutorial mode.

    The stderr handler writes messages at ``WARNING`` and above.

    Calling this function multiple times is safe: existing root handlers are
    removed and closed before new handlers are installed.

    Args:
        level (str): Logging level name (e.g., ``"DEBUG"``, ``"INFO"``).
        is_tutorial (bool): If True, use deterministic timestamps and overwrite the log
            file each run.

    Raises:
        ValueError: If ``level`` is not a valid logging level name.
    """
    # route Python warnings through logging.
    logging.captureWarnings(True)
    warn_logger = logging.getLogger("py.warnings")

    # normalize and validate level
    level_upper = level.upper()
    numeric_level = getattr(logging, level_upper, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level!r}")

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # avoid duplicated logs if configure_logging is called more than once
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        finally:
            pass

    # base class for StreamHandler and RotatingFileHandler allowing both to type check out
    handler: logging.Handler

    # let warnings flow to root handlers (avoid duplicates)
    warn_logger.handlers.clear()
    warn_logger.propagate = True

    # create err handler (WARNING and above)
    err_handler = logging.StreamHandler(stream=sys.stderr)
    err_handler.setLevel("WARNING")
    _set_formatter(err_handler, is_tutorial=is_tutorial)
    root.addHandler(err_handler)

    # define and create folder for saving log
    log_file = pathlib.Path("compliance").with_suffix(".log")
    fn = _default_log_dir() / log_file

    try:
        # for tutorial we don't want setup tests to be written to the log file,
        # so we use write mode and only keep the last written log
        if is_tutorial:
            handler = logging.FileHandler(filename=fn, mode="w")
        else:
            handler = RotatingFileHandler(
                filename=fn, mode="a", maxBytes=50 * 1024 * 1024, backupCount=2
            )
    except OSError as exc:
        root.warning("Could not configure file logging at %s: %s", fn, exc)
        return

    # create debug handler (all messages)
    _set_formatter(handler, is_tutorial=is_tutorial)
    root.addHandler(handler)
    handler.setLevel(numeric_level)


def _set_formatter(handler: logging.Handler, *, is_tutorial: bool = False) -> None:
    # in tutorial mode set fixed datetime for deterministic log
    datetime = "2000-01-01T00:00:00+0100" if is_tutorial else "{asctime}"
    handler.setFormatter(
        logging.Formatter(
            fmt=datetime + " {levelname} {name}: {message}",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
            style="{",
        )
    )


def _default_log_dir() -> pathlib.Path:
    """Return an OS-appropriate log directory."""
    if os.name == "nt":
        localappdata = os.getenv("LOCALAPPDATA")
        base = (
            pathlib.Path(localappdata)
            if localappdata is not None
            else pathlib.Path.home() / "AppData" / "Local"
        )
    else:
        xdg_state_home = os.getenv("XDG_STATE_HOME")
        base = (
            pathlib.Path(xdg_state_home)
            if xdg_state_home is not None
            else pathlib.Path.home() / ".local" / "state"
        )

    log_dir = base / "compliance" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    return log_dir
