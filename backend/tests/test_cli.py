import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from compliance import cli
from compliance.services.schemas import UserOut

TEST_PASSWORD = "correct-password"  # noqa: S105


class TestRagCli:
    def test_parse_boe_refuses_existing_output_without_fetching(
        self, monkeypatch, tmp_path, capsys
    ) -> None:
        parsed_dir = tmp_path / "parsed_boes"
        parsed_dir.mkdir()
        output_path = parsed_dir / "BOE-A-2018-16673.json"
        output_path.write_text("{}", encoding="utf-8")
        fetch = MagicMock()

        monkeypatch.setattr(cli, "PARSED_BOES_DIR", parsed_dir)
        monkeypatch.setattr(cli, "fetch_boe_regulation", fetch)

        result = cli.main(["rag", "parse-boe", "--boe-id", "BOE-A-2018-16673"])

        captured = capsys.readouterr()
        assert result == 1
        assert "already exists" in captured.err
        fetch.assert_not_called()

    def test_parse_boe_writes_default_output_when_overwrite_is_passed(
        self, monkeypatch, tmp_path, capsys
    ) -> None:
        parsed_dir = tmp_path / "parsed_boes"
        document = {"id": "BOE-A-2018-16673", "structure": []}

        monkeypatch.setattr(cli, "PARSED_BOES_DIR", parsed_dir)
        monkeypatch.setattr(cli, "fetch_boe_regulation", MagicMock(return_value={}))
        monkeypatch.setattr(
            cli, "parse_boe_regulation", MagicMock(return_value=document)
        )

        result = cli.main(
            ["rag", "parse-boe", "--boe-id", "BOE-A-2018-16673", "--overwrite"]
        )

        captured = capsys.readouterr()
        output_path = parsed_dir / "BOE-A-2018-16673.json"
        assert result == 0
        assert json.loads(output_path.read_text(encoding="utf-8")) == document
        assert f"Saved parsed BOE to: {output_path.resolve()}" in captured.out

    def test_extract_clauses_processes_all_parsed_jsons_and_overwrites_outputs(
        self, tmp_path, capsys
    ) -> None:
        input_dir = tmp_path / "parsed_boes"
        output_dir = tmp_path / "clauses"
        input_dir.mkdir()
        output_dir.mkdir()
        document = {
            "id": "document-id",
            "structure": [
                {
                    "type": "article",
                    "number": "1",
                    "title": "Purpose",
                    "text": " First clause. ",
                    "children": [],
                }
            ],
        }
        (input_dir / "BOE-A.json").write_text(
            json.dumps(document),
            encoding="utf-8",
        )
        (input_dir / "BOE-B.json").write_text(
            json.dumps(document),
            encoding="utf-8",
        )
        (output_dir / "BOE-A.json").write_text("old", encoding="utf-8")

        result = cli.main(
            [
                "rag",
                "extract-clauses",
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(output_dir),
            ]
        )

        captured = capsys.readouterr()
        boe_a_clauses = json.loads((output_dir / "BOE-A.json").read_text("utf-8"))
        boe_b_clauses = json.loads((output_dir / "BOE-B.json").read_text("utf-8"))
        assert result == 0
        assert len(boe_a_clauses) == 1
        assert len(boe_b_clauses) == 1
        assert boe_a_clauses[0]["text"] == "First clause."
        assert "Created 2 clauses from 2 files." in captured.out

    def test_extract_clauses_returns_error_for_malformed_json(
        self, tmp_path, capsys
    ) -> None:
        input_dir = tmp_path / "parsed_boes"
        output_dir = tmp_path / "clauses"
        input_dir.mkdir()
        (input_dir / "broken.json").write_text("{", encoding="utf-8")

        result = cli.main(
            [
                "rag",
                "extract-clauses",
                "--input-dir",
                str(input_dir),
                "--output-dir",
                str(output_dir),
            ]
        )

        captured = capsys.readouterr()
        assert result == 1
        assert "Clause extraction failed for" in captured.err
        assert "broken.json" in captured.err


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
