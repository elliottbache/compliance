from types import SimpleNamespace
from unittest.mock import MagicMock

from compliance import cli
from compliance.services.schemas import UserOut

TEST_PASSWORD = "correct-password"  # noqa: S105


class TestBootstrapAdmin:
    def test_returns_error_when_password_is_empty(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(cli.getpass, "getpass", MagicMock(return_value=""))

        result = cli.main(
            [
                "bootstrap-admin",
                "--full-name",
                "Alice Admin",
                "--email",
                "admin@example.com",
            ]
        )

        captured = capsys.readouterr()
        assert result == 1
        assert "Admin password cannot be empty." in captured.err

    def test_returns_error_when_passwords_do_not_match(
        self, monkeypatch, capsys
    ) -> None:
        monkeypatch.setattr(
            cli.getpass,
            "getpass",
            MagicMock(side_effect=[TEST_PASSWORD, "different-password"]),
        )

        result = cli.main(
            [
                "bootstrap-admin",
                "--full-name",
                "Alice Admin",
                "--email",
                "admin@example.com",
            ]
        )

        captured = capsys.readouterr()
        assert result == 1
        assert "Admin passwords do not match." in captured.err

    def test_calls_service_with_parsed_args_when_passwords_match(
        self, monkeypatch, capsys
    ) -> None:
        session = MagicMock()
        session_context = MagicMock()
        session_context.__enter__.return_value = session
        session_context.__exit__.return_value = None
        mock_bootstrap = MagicMock(
            return_value=SimpleNamespace(
                created=True,
                user=UserOut(
                    id=1,
                    full_name="Alice Admin",
                    email="admin@example.com",
                    role="admin",
                    is_active=True,
                    created_at="2026-06-26T12:00:00Z",
                ),
            )
        )
        monkeypatch.setattr(
            cli.getpass,
            "getpass",
            MagicMock(side_effect=[TEST_PASSWORD, TEST_PASSWORD]),
        )
        monkeypatch.setattr(cli, "get_engine", MagicMock(return_value="engine"))
        monkeypatch.setattr(cli, "Session", MagicMock(return_value=session_context))
        monkeypatch.setattr(cli, "bootstrap_first_admin", mock_bootstrap)

        result = cli.main(
            [
                "bootstrap-admin",
                "--full-name",
                "Alice Admin",
                "--email",
                "admin@example.com",
            ]
        )

        captured = capsys.readouterr()
        assert result == 0
        assert "Created first admin user: admin@example.com" in captured.out
        mock_bootstrap.assert_called_once_with(
            session,
            full_name="Alice Admin",
            email="admin@example.com",
            password=TEST_PASSWORD,
        )

    def test_prints_noop_message_when_active_admin_exists(
        self, monkeypatch, capsys
    ) -> None:
        session_context = MagicMock()
        session_context.__enter__.return_value = MagicMock()
        session_context.__exit__.return_value = None
        monkeypatch.setattr(
            cli.getpass,
            "getpass",
            MagicMock(side_effect=[TEST_PASSWORD, TEST_PASSWORD]),
        )
        monkeypatch.setattr(cli, "get_engine", MagicMock(return_value="engine"))
        monkeypatch.setattr(cli, "Session", MagicMock(return_value=session_context))
        monkeypatch.setattr(
            cli,
            "bootstrap_first_admin",
            MagicMock(return_value=SimpleNamespace(created=False, user=None)),
        )

        result = cli.main(
            [
                "bootstrap-admin",
                "--full-name",
                "Alice Admin",
                "--email",
                "admin@example.com",
            ]
        )

        captured = capsys.readouterr()
        assert result == 0
        assert "Active admin user already exists; no user created." in captured.out
