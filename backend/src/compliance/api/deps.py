"""FastAPI dependency aliases used by route modules."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from compliance.db.db_access import get_db

SessionDep = Annotated[Session, Depends(get_db)]
