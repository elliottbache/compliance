"""FastAPI application entrypoint for compliance API routes."""

from fastapi import FastAPI

from compliance.api.routers import (
    attachments,
    certifications,
    certifiers,
    clients,
    findings,
    rules,
    sites,
)
from compliance.logging_utils import configure_logging

configure_logging(level="DEBUG")

app = FastAPI()
app.include_router(sites.router)
app.include_router(certifications.router)
app.include_router(findings.router)
app.include_router(attachments.router)
app.include_router(clients.router)
app.include_router(certifiers.router)
app.include_router(rules.router)
