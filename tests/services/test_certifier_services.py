from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    CertifierCreate,
)
from compliance.db.models import Certifier
from compliance.services.certifiers import (
    CertifierConflictError,
    CertifierOrganizationNameConflictError,
    get_certifier_by_id,
    get_certifiers,
    post_new_certifier,
)


def _certifier(**overrides) -> Certifier:
    certifier = Certifier(
        id=10,
        organization_name="SafeCheck Inc.",
    )
    for key, value in overrides.items():
        setattr(certifier, key, value)
    return certifier


class TestGetCertifiers:
    def test_returns_certifiers_from_session(self) -> None:
        session = MagicMock()
        certifiers = [
            _certifier(id=10, organization_name="SafeCheck Inc."),
            _certifier(id=11, organization_name="VoltGuard"),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = certifiers

        result = get_certifiers(session, limit=10, offset=5)

        assert result == certifiers

    def test_orders_certifiers_by_organization_name_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_certifiers(session, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY certifiers.organization_name, certifiers.id" in str(stmt)


class TestGetCertifierById:
    def test_returns_certifier_when_found(self) -> None:
        session = MagicMock()
        certifier = _certifier()
        session.get.return_value = certifier

        result = get_certifier_by_id(10, session)

        assert result is certifier
        session.get.assert_called_once_with(Certifier, 10)

    def test_returns_none_when_certifier_is_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_certifier_by_id(10, session)

        assert result is None
        session.get.assert_called_once_with(Certifier, 10)


class TestPostNewCertifier:
    def test_adds_and_commits_new_certifier(self) -> None:
        session = MagicMock()
        certifier = CertifierCreate(organization_name="SafeCheck Inc.")

        post_new_certifier(certifier, session)

        session.add.assert_called_once()
        added_certifier = session.add.call_args.args[0]

        assert isinstance(added_certifier, Certifier)
        assert added_certifier.organization_name == "SafeCheck Inc."

    def test_rolls_back_and_raises_organization_name_conflict_when_name_exists(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        certifier = CertifierCreate(organization_name="SafeCheck Inc.")
        monkeypatch.setattr(
            "compliance.services.certifiers.get_constraint_name",
            lambda exc: "uq_organization_name",
        )

        with pytest.raises(CertifierOrganizationNameConflictError):
            post_new_certifier(certifier, session)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_rolls_back_and_raises_generic_conflict_for_unknown_integrity_error(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        certifier = CertifierCreate(organization_name="SafeCheck Inc.")
        monkeypatch.setattr(
            "compliance.services.certifiers.get_constraint_name",
            lambda exc: "unexpected_constraint",
        )

        with pytest.raises(CertifierConflictError):
            post_new_certifier(certifier, session)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()
