from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
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
)


def _rule(**overrides) -> Rule:
    rule = Rule(
        id=20,
        regulation_id=3,
        rule_index="FS-101",
        title="Equipment Maintenance",
        description="Equipment must be maintained.",
    )
    for key, value in overrides.items():
        setattr(rule, key, value)
    return rule


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
    def test_returns_rules_from_session(self) -> None:
        session = MagicMock()
        rules = [
            _rule(id=20),
            _rule(id=21, rule_index="FS-102"),
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

    def test_excludes_archived_rules_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_rules(session, regulation_id=None, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "rules.archived_at IS NULL" in str(stmt)
        assert "regulations.archived_at IS NULL" in str(stmt)

    def test_includes_archived_rules_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_rules(
            session,
            regulation_id=None,
            limit=None,
            offset=0,
            include_archived=True,
        )

        stmt = session.execute.call_args.args[0]
        assert "rules.archived_at IS NULL" not in str(stmt)
        assert "regulations.archived_at IS NULL" not in str(stmt)

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

        result = get_rule_by_id(20, session)

        stmt = session.execute.call_args.args[0]
        assert "JOIN regulations" in str(stmt)
        assert "rules.id = :id_1" in str(stmt)
        assert result is expected_rule

    def test_returns_none_when_rule_is_not_found(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        result = get_rule_by_id(999, session)

        session.execute.assert_called_once()
        assert result is None

    def test_returns_none_when_rule_is_archived_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        result = get_rule_by_id(20, session)

        stmt = session.execute.call_args.args[0]
        assert "rules.archived_at IS NULL" in str(stmt)
        assert "regulations.archived_at IS NULL" in str(stmt)
        assert result is None

    def test_returns_archived_rule_when_requested(self) -> None:
        session = MagicMock()
        rule = _rule(archived_at=datetime(2026, 5, 7))
        session.execute.return_value.scalar_one_or_none.return_value = rule

        result = get_rule_by_id(20, session, include_archived=True)

        stmt = session.execute.call_args.args[0]
        assert "rules.archived_at IS NULL" not in str(stmt)
        assert "regulations.archived_at IS NULL" not in str(stmt)
        assert result is rule


class TestPostNewRule:
    def test_adds_and_commits_new_rule(self) -> None:
        session = MagicMock()
        rule = _rule_create()

        result = post_new_rule(rule, session)

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
            post_new_rule(_rule_create(), session)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_raises_regulation_error_when_regulation_does_not_exist(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error("rules_regulation_id_fkey")

        with pytest.raises(RuleRegulationNotFoundError):
            post_new_rule(_rule_create(), session)

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
            post_new_rule(_rule_create(), session)

        session.rollback.assert_called_once_with()
