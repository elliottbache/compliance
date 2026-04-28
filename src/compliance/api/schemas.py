from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SiteOutput(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    nif: str = Field(min_length=9, max_length=9)
    city: str
    postal_code: int
    street: str
    street_number: int | None
    suite: str | None
    address_info: str | None


class CertificationOutput(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    certifier_id: int
    regulation_id: int
    site_id: int
    result: str | None
    inspection_date: date | None
    resolution_date: date | None
