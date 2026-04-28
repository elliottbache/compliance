from sqlalchemy.orm import Session

from compliance.db.models import Site


def get_site_by_id(site_id: int, session: Session) -> Site | None:
    return session.get(Site, site_id)
