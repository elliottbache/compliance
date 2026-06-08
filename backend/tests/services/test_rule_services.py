from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from compliance.db.models import Regulation, Rule
from compliance.services.rules import (
    RuleConflictError,
    RuleIndexConflictError,
    RuleRegulationNotFoundError,
    get_rules,
    post_new_rule,
    post_rule_archived_by_id,
    post_rule_restored_by_id,
)
from compliance.services.schemas import (
    ArchiveRequest,
    RuleCreate,
    RuleOut,
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
        self, sqlite_session, db_factory, rule_row_factory, archived_fields
    ) -> None:
        db_factory()

        archived = rule_row_factory(
            id=21,
            rule_index="FS-102",
            **archived_fields("merged"),
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        rules = get_rules(sqlite_session, regulation_id=None, limit=None, offset=0)

        assert [rule.id for rule in rules] == [5]

    def test_includes_archived_rules_when_requested(
        self, sqlite_session, db_factory, rule_row_factory, archived_fields
    ) -> None:
        db_factory()
        archived = rule_row_factory(
            id=21,
            rule_index="FS-102",
            **archived_fields("merged"),
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

    def test_rolls_back_and_raises_conflict_when_insert_conflicts(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory()

        with pytest.raises(RuleConflictError):
            post_new_rule(session, _rule_create())

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_raises_rule_index_conflict_when_rule_index_already_exists(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory(
            "uq_rules_regulation_id_rule_index"
        )

        with pytest.raises(RuleIndexConflictError):
            post_new_rule(session, _rule_create())

        session.rollback.assert_called_once_with()


class TestPostRuleArchivedById:
    def test_archives_rule_with_stripped_reason(
        self, rule_row_factory, assert_archived_record
    ) -> None:
        session = MagicMock()
        rule = rule_row_factory()
        session.get.return_value = rule

        result = post_rule_archived_by_id(
            session,
            5,
            archive_request=ArchiveRequest(archive_reason="  duplicate  "),
        )

        assert result is rule
        assert_archived_record(rule, "duplicate")
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
    def test_restores_archived_rule(
        self, rule_row_factory, assert_restored_record
    ) -> None:
        session = MagicMock()
        rule = rule_row_factory(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="old",
        )
        session.get.return_value = rule

        result = post_rule_restored_by_id(session, 5)

        assert result is rule
        assert_restored_record(rule)
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
    def test_raises_regulation_error_when_regulation_does_not_exist(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory(
            "fk_rules_regulation_id_regulations"
        )

        with pytest.raises(RuleRegulationNotFoundError):
            post_new_rule(session, _rule_create())

        session.rollback.assert_called_once_with()


class TestPostRuleArchiveRestoreIntegration:
    def test_archive_then_restore_works(
        self, sqlite_session, db_factory, assert_archive_restore_round_trip
    ) -> None:
        db_factory()

        assert_archive_restore_round_trip(
            sqlite_session,
            5,
            archive_fn=post_rule_archived_by_id,
            restore_fn=post_rule_restored_by_id,
        )
