from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    ArchiveRequest,
    RuleCreate,
    RuleOut,
)
from compliance.db.models import Regulation, Rule
from compliance.services.rules import (
    RuleConflictError,
    RuleIndexConflictError,
    RuleRegulationNotFoundError,
    get_rule_by_id,
    get_rules,
    post_new_rule,
    post_rule_archived_by_id,
    post_rule_restored_by_id,
)


def _rule_create(**overrides) -> RuleCreate:
    data = {
        "regulation_id": 3,
        "rule_index": "FS-101",
        "title": "Equipment Maintenance",
        "description": "Equipment must be maintained.",
    }
    data.update(overrides)
    return RuleCreate(**data)


def _integrity_error(constraint_name: str | None = None) -> IntegrityError:
    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))
    return IntegrityError("insert failed", {}, orig)


class TestGetRules:
    def test_returns_rules_from_session(self, rule_row_factory) -> None:
        session = MagicMock()
        rules = [
            rule_row_factory(),
            rule_row_factory(id=21, rule_index="FS-102"),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = rules

        result = get_rules(session, regulation_id=None, limit=10, offset=5)

        assert result == [RuleOut.model_validate(rule) for rule in rules]

    def test_orders_rules_by_regulation_rule_index_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_rules(session, regulation_id=None, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY rules.regulation_id, rules.rule_index, rules.id" in str(stmt)

    def test_excludes_archived_rules_by_default(
        self, sqlite_session, db_factory, rule_row_factory
    ) -> None:
        db_factory()

        archived = rule_row_factory(
            id=21,
            rule_index="FS-102",
            archived_at=datetime.now(UTC),
            archive_reason="merged",
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        rules = get_rules(sqlite_session, regulation_id=None, limit=None, offset=0)

        assert [rule.id for rule in rules] == [5]

    def test_includes_archived_rules_when_requested(
        self, sqlite_session, db_factory, rule_row_factory
    ) -> None:
        db_factory()
        archived = rule_row_factory(
            id=21,
            rule_index="FS-102",
            archived_at=datetime.now(UTC),
            archive_reason="merged",
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        rules = get_rules(
            sqlite_session,
            regulation_id=None,
            limit=None,
            offset=0,
            include_archived=True,
        )

        returned_ids = {rule.id for rule in rules}
        assert returned_ids == {5, 21}

    def test_filters_by_regulation_when_regulation_exists(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Regulation)
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = get_rules(session, regulation_id=3, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert result == []
        session.get.assert_called_once_with(Regulation, 3)
        assert "rules.regulation_id = :regulation_id_1" in str(stmt)

    def test_returns_none_when_regulation_filter_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_rules(session, regulation_id=999, limit=None, offset=0)

        assert result is None
        session.get.assert_called_once_with(Regulation, 999)
        session.execute.assert_not_called()


class TestGetRuleById:
    def test_gets_rule_by_id_from_session(self) -> None:
        session = MagicMock()
        expected_rule = MagicMock(spec=Rule)
        session.execute.return_value.scalar_one_or_none.return_value = expected_rule

        result = get_rule_by_id(session, 20)

        stmt = session.execute.call_args.args[0]
        assert "JOIN regulations" in str(stmt)
        assert "rules.id = :id_1" in str(stmt)
        assert result is expected_rule

    def test_returns_none_when_rule_is_not_found(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        result = get_rule_by_id(session, 999)

        session.execute.assert_called_once()
        assert result is None

    def test_includes_archived_rule_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            rule_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        result = get_rule_by_id(sqlite_session, 5)

        assert result is not None
        assert result.archive_reason == "closed"

    def test_returns_none_when_archived_rule_excluded(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            rule_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        result = get_rule_by_id(sqlite_session, 5, include_archived=False)

        assert result is None


class TestPostNewRule:
    def test_adds_and_commits_new_rule(self) -> None:
        session = MagicMock()
        rule = _rule_create()

        result = post_new_rule(session, rule)

        session.add.assert_called_once()
        added_rule = session.add.call_args.args[0]

        assert result is added_rule
        assert isinstance(added_rule, Rule)
        assert added_rule.regulation_id == 3
        assert added_rule.rule_index == "FS-101"
        assert added_rule.title == "Equipment Maintenance"
        assert added_rule.description == "Equipment must be maintained."

    def test_rolls_back_and_raises_conflict_when_insert_conflicts(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error()

        with pytest.raises(RuleConflictError):
            post_new_rule(session, _rule_create())

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    @pytest.mark.parametrize(
        "constraint_name",
        [
            "uq_regulation_id_rule_index",
            "uq_rules_regulation_id_rule_index",
        ],
    )
    def test_raises_rule_index_conflict_when_rule_index_already_exists(
        self, constraint_name
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error(constraint_name)

        with pytest.raises(RuleIndexConflictError):
            post_new_rule(session, _rule_create())

        session.rollback.assert_called_once_with()


class TestPostRuleArchivedById:
    def test_archives_rule_with_stripped_reason(self, rule_row_factory) -> None:
        session = MagicMock()
        rule = rule_row_factory()
        session.get.return_value = rule

        result = post_rule_archived_by_id(
            session,
            5,
            archive_request=ArchiveRequest(archive_reason="  duplicate  "),
        )

        assert result is rule
        assert rule.archived_at is not None
        assert rule.archived_at.tzinfo is UTC
        assert rule.archive_reason == "duplicate"
        session.get.assert_called_once_with(Rule, 5)
        session.commit.assert_called_once_with()

    def test_does_not_rearchive_existing_archived_rule(self, rule_row_factory) -> None:
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        session = MagicMock()
        rule = rule_row_factory(archived_at=archived_at, archive_reason="old")
        session.get.return_value = rule

        result = post_rule_archived_by_id(
            session, 5, archive_request=ArchiveRequest(archive_reason="new")
        )

        assert result is rule
        assert rule.archived_at == archived_at
        assert rule.archive_reason == "old"
        session.commit.assert_not_called()

    def test_returns_none_when_rule_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_rule_archived_by_id(session, 20, archive_request=ArchiveRequest())

        assert result is None
        session.get.assert_called_once_with(Rule, 20)
        session.commit.assert_not_called()


class TestPostRuleRestoredById:
    def test_restores_archived_rule(self, rule_row_factory) -> None:
        session = MagicMock()
        rule = rule_row_factory(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="old",
        )
        session.get.return_value = rule

        result = post_rule_restored_by_id(session, 5)

        assert result is rule
        assert rule.archived_at is None
        assert rule.archive_reason is None
        session.get.assert_called_once_with(Rule, 5)
        session.commit.assert_called_once_with()

    def test_returns_active_rule_without_commit(self, rule_row_factory) -> None:
        session = MagicMock()
        rule = rule_row_factory(archived_at=None, archive_reason=None)
        session.get.return_value = rule

        result = post_rule_restored_by_id(session, 20)

        assert result is rule
        session.commit.assert_not_called()

    def test_returns_none_when_rule_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_rule_restored_by_id(session, 20)

        assert result is None
        session.get.assert_called_once_with(Rule, 20)
        session.commit.assert_not_called()


class TestPostNewRuleConflicts:
    def test_raises_regulation_error_when_regulation_does_not_exist(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error("rules_regulation_id_fkey")

        with pytest.raises(RuleRegulationNotFoundError):
            post_new_rule(session, _rule_create())

        session.rollback.assert_called_once_with()


class TestPostRuleArchiveRestoreIntegration:
    def test_archive_then_restore_works(
        self, sqlite_session, db_factory, rule_row_factory
    ) -> None:
        db_factory()

        archived = post_rule_archived_by_id(
            sqlite_session,
            5,
            archive_request=ArchiveRequest(archive_reason=" duplicate "),
        )
        archived = post_rule_archived_by_id(
            sqlite_session,
            5,
            archive_request=ArchiveRequest(archive_reason=" second "),
        )
        assert archived is not None
        assert archived.archived_at is not None
        assert archived.archive_reason == "duplicate"

        restored = post_rule_restored_by_id(sqlite_session, 5)

        assert restored is not None
        assert restored.archived_at is None
        assert restored.archive_reason is None
