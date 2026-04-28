from unittest.mock import MagicMock

from compliance.db.models import Certification, Site
from compliance.services.query_db import get_certification_by_id, get_site_by_id


class TestGetSiteById:
    def test_gets_site_by_id_from_session(self) -> None:
        session = MagicMock()
        expected_site = MagicMock(spec=Site)
        session.get.return_value = expected_site

        result = get_site_by_id(12, session)

        session.get.assert_called_once_with(Site, 12)
        assert result is expected_site

    def test_returns_none_when_site_is_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_site_by_id(999, session)

        session.get.assert_called_once_with(Site, 999)
        assert result is None


class TestGetCertificationById:
    def test_gets_certification_by_id_from_session(self) -> None:
        session = MagicMock()
        expected_certification = MagicMock(spec=Certification)
        session.get.return_value = expected_certification

        result = get_certification_by_id(42, session)

        session.get.assert_called_once_with(Certification, 42)
        assert result is expected_certification

    def test_returns_none_when_certification_is_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_certification_by_id(999, session)

        session.get.assert_called_once_with(Certification, 999)
        assert result is None
