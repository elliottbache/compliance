from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    RegulationCreate,
    RegulationOut,
)
from compliance.db.models import Certifier, Regulation
from compliance.services.regulations import (
    RegulationConflictError,
    RegulationTitleConflictError,
    get_regulation_by_id,
    get_regulations,
    post_new_regulation,
)


def _regulation(**overrides) -> Regulation:
    regulation = Regulation(
        id=3,
        title="Fire Safety 2026",
        description="Fire safety requirements for commercial sites.",
        published_date=date(2026, 1, 15),
    )
    for key, value in overrides.items():
        setattr(regulation, key, value)
    return regulation


def _regulation_create(**overrides) -> RegulationCreate:
    data = {
        "title": "Fire Safety 2026",
        "description": "Fire safety requirements for commercial sites.",
        "published_date": date(2026, 1, 15),
    }
    data.update(overrides)
    return RegulationCreate(**data)


def _integrity_error(constraint_name: str | None = None) -> IntegrityError:
    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))
    return IntegrityError("insert failed", {}, orig)


class TestGetRegulations:
    def test_returns_regulations_from_session(self) -> None:
        session = MagicMock()
        regulations = [
            _regulation(id=3),
            _regulation(id=4, title="Electrical Safety 2026"),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = regulations

        result = get_regulations(session, certifier_id=None, limit=10, offset=5)

        assert result == [
            RegulationOut.model_validate(regulation) for regulation in regulations
        ]

    def test_orders_regulations_by_published_date_title_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_regulations(session, certifier_id=None, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert (
            "ORDER BY regulations.published_date DESC, "
            "regulations.title, regulations.id" in str(stmt)
        )

    def test_excludes_archived_regulations_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_regulations(session, certifier_id=None, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "regulations.archived_at IS NULL" in str(stmt)

    def test_includes_archived_regulations_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_regulations(
            session,
            certifier_id=None,
            limit=None,
            offset=0,
            include_archived=True,
        )

        stmt = session.execute.call_args.args[0]
        assert "regulations.archived_at IS NULL" not in str(stmt)

    def test_filters_by_certifier_when_certifier_exists(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Certifier)
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = get_regulations(session, certifier_id=7, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert result == []
        session.get.assert_called_once_with(Certifier, 7)
        assert "certifications.certifier_id = :certifier_id_1" in str(stmt)
        assert "DISTINCT" in str(stmt)

    def test_returns_none_when_certifier_filter_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_regulations(session, certifier_id=999, limit=None, offset=0)

        assert result is None
        session.get.assert_called_once_with(Certifier, 999)
        session.execute.assert_not_called()


class TestGetRegulationById:
    def test_gets_regulation_by_id_from_session(self) -> None:
        session = MagicMock()
        expected_regulation = MagicMock(spec=Regulation)
        session.get.return_value = expected_regulation

        result = get_regulation_by_id(3, session)

        session.get.assert_called_once_with(Regulation, 3)
        assert result is expected_regulation

    def test_returns_none_when_regulation_is_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_regulation_by_id(999, session)

        session.get.assert_called_once_with(Regulation, 999)
        assert result is None

    def test_returns_none_when_regulation_is_archived_by_default(self) -> None:
        session = MagicMock()
        regulation = _regulation(archived_at=datetime(2026, 5, 7))
        session.get.return_value = regulation

        result = get_regulation_by_id(3, session)

        assert result is None

    def test_returns_archived_regulation_when_requested(self) -> None:
        session = MagicMock()
        regulation = _regulation(archived_at=datetime(2026, 5, 7))
        session.get.return_value = regulation

        result = get_regulation_by_id(3, session, include_archived=True)

        assert result is regulation


class TestPostNewRegulation:
    def test_adds_and_commits_new_regulation(self) -> None:
        session = MagicMock()
        regulation = _regulation_create()

        result = post_new_regulation(regulation, session)

        session.add.assert_called_once()
        added_regulation = session.add.call_args.args[0]

        assert result is added_regulation
        assert isinstance(added_regulation, Regulation)
        assert added_regulation.title == "Fire Safety 2026"
        assert (
            added_regulation.description
            == "Fire safety requirements for commercial sites."
        )
        assert added_regulation.published_date == date(2026, 1, 15)

    def test_rolls_back_and_raises_conflict_when_insert_conflicts(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error()

        with pytest.raises(RegulationConflictError):
            post_new_regulation(_regulation_create(), session)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_raises_title_conflict_when_title_already_exists(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error("uq_title")

        with pytest.raises(RegulationTitleConflictError):
            post_new_regulation(_regulation_create(), session)

        session.rollback.assert_called_once_with()
