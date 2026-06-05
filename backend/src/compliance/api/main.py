"""FastAPI application entrypoint for compliance API routes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from compliance.api.routers import (
    attachments,
    certifications,
    certifiers,
    clients,
    findings,
    regulations,
    rules,
    sites,
    users,
)
from compliance.logging_utils import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Configure app-level resources when FastAPI starts."""
    configure_logging(level="DEBUG")
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(sites.router)
app.include_router(certifications.router)
app.include_router(findings.router)
app.include_router(attachments.router)
app.include_router(clients.router)
app.include_router(certifiers.router)
app.include_router(rules.router)
app.include_router(regulations.router)
app.include_router(users.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
