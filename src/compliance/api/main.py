from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from compliance.api.schemas import SiteOutput
from compliance.db.db_access import get_db
from compliance.services.query_db import get_site_by_id

app = FastAPI()


SessionDep = Annotated[Session, Depends(get_db)]


@app.get("/sites/{site_id}")
def get_site_by_id_route(site_id: int, session: SessionDep) -> SiteOutput:
    site = get_site_by_id(site_id, session)
    if site is None:
        raise HTTPException(
            status_code=404, detail=f"No site for this id found: {site_id}"
        )

    return SiteOutput.model_validate(site)


"""Exercise 4 — Add GET /certifications/{certification_id}

Return one certification.

Good practice:

include the main factual fields only
do not embed full nested history yet"""


"""@app.get("/certifications/{certification_id}")
def get_certification_by_id_route(
    certification_id: int, session: SessionDep
) -> CertificationOutput:
    certification = get_certification_by_id(certification_id, session)
    if certification is None:
        raise HTTPException(f"No certification for this id: {certificaion_id}")

    return certification
"""
