from sqlalchemy.orm import Session

from compliance.db.models import Certification, Site


def get_site_by_id(site_id: int, session: Session) -> Site | None:
    return session.get(Site, site_id)


def get_certification_by_id(
    certification_id: int, session: Session
) -> Certification | None:
    return session.get(Certification, certification_id)
