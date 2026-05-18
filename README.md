# AI-integrated Compliance Database Tool

## IN PROGRESS!!!  USE AT YOUR OWN RISK!!!

[![CI](https://github.com/elliottbache/compliance/actions/workflows/ci.yaml/badge.svg)](https://github.com/elliottbache/compliance/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/github/elliottbache/compliance/graph/badge.svg?token=kNwbaexX4N)](https://codecov.io/github/elliottbache/compliance)
[![Release](https://img.shields.io/github/v/release/elliottbache/compliance)](https://github.com/elliottbache/compliance/releases)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm_NC_1.0.0-525252?style=flat-square)](https://polyformproject.org/licenses/noncommercial/1.0.0/)

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-blue?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-psycopg2-blue?logo=postgresql&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-blue)
![Alembic](https://img.shields.io/badge/Alembic-migrations-blue)
![Anthropic](https://img.shields.io/badge/AI-Anthropic-blue)
![React](https://img.shields.io/badge/React-19-blue?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6-blue?logo=vite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker&logoColor=white)
![Make](https://img.shields.io/badge/Make-automation-blue)
![pytest](https://img.shields.io/badge/tests-pytest-blue?logo=pytest&logoColor=white)
![ruff](https://img.shields.io/badge/lint-ruff-blue)
![black](https://img.shields.io/badge/format-black-blue)
![mypy](https://img.shields.io/badge/types-mypy-blue)
![Sphinx](https://img.shields.io/badge/docs-Sphinx-blue?logo=sphinx&logoColor=white)

## Short description
This project is a backend-first inspection and compliance management system designed to keep 
certification history, findings, rules, evidence, and site records organized in one place. 
Its goal is to improve traceability, make historical reviews easier, and support faster, more 
consistent report generation without replacing human technical judgment. Over time, it is 
intended to add tightly controlled AI assistance for tasks like summarization, drafting, and 
comparison of past certifications while keeping factual retrieval and validation in code.

## Frontend

The frontend is a thin React/Vite/TypeScript dashboard for the compliance MVP. It expects the FastAPI backend to be running separately.

### Requirements

- Node.js / npm
- Running FastAPI backend at `http://localhost:8000`

### Setup

From the repository root:

    cd frontend
    npm install
    cp .env.example .env

On Windows PowerShell:

    cd frontend
    npm install
    Copy-Item .env.example .env

### Environment variables

`frontend/.env` should contain:

    VITE_API_BASE_URL=http://localhost:8000

Change this value if the backend runs on another host or port.

### Run locally

Start the backend first, for example:

    uvicorn compliance.api.main:app --reload

Then start the frontend:

    cd frontend
    npm run dev

Open:

    http://localhost:5173

### Build check

    cd frontend
    npm run build

### Notes

The frontend does not run AI automatically. AI analysis is only requested when the user clicks **Run AI Analysis**. Generated Markdown is created from the currently loaded AI analysis in browser state and is not persisted after page refresh.

## TODO
- Add technology badges
- Add local model option to use for site analysis.
- Add privacy for Anthropic and write guide in README.
- Add LLM function to return differences in regulation since last visit.
- Add stop_reason: "refusal" and stop_reason: "max_tokens" and others to requerying on failure in anthropic_api.py
- Add migration
- Add LLM to parse regulation into database.
- Add LLM to compare current regulation with last regulation
- Add MCP and hosting?
- Add sanitizer for files and delete those that are not linked to an attachment in the db
- Add check to db so that if uploaded_at is not null then there must be a file_path for attachments
- Add a better drop-down list for attachment downloads (and uploads).  Perhaps using search bar or using checkboxes.

## Database description
### Notes
- Historical records are not hard-deleted by normal users.
- Important records are archived or deletion-restricted.
- Finding-attachment links are managed through finding and attachment creation endpoints. Standalone link CRUD is deferred until there is a real UX need.

#### Archive Policy
- All main domain records support archive/restore through archived_at and archive_reason.
- List endpoints exclude archived records by default and expose include_archived=false/true.
- Detail endpoints return archived records by ID.
- FindingAttachment is not archived; link rows may be deleted because they do not delete evidence.
- Hard delete endpoints are deferred for MVP.
- Child rows are not archived when a parent row is archived.  Using ``include_archived = False``, only child rows with non-archived parents are shown.
- Merge row factories in tests into higher-level conftest.py
- Change default row factory values to be interrelated
- Global list endpoints exclude archived records by default and support `include_archived=true`.
- When `include_archived=true`, archived records are included. For filtered list endpoints, this also allows archived parent context where already implemented. Example: `GET /sites?nif=...&include_archived=true` may return sites for an archived client.
- Exact detail endpoints may return archived records by ID, because archived records remain part of the audit trail and are not deleted. Responses expose `archived_at` and `archive_reason`.
- Archive/restore endpoints are idempotent: archiving an already archived record returns `200` unchanged, and restoring an already active record returns `200` unchanged.
- Archive/restore does not cascade. Archiving a client/site/certification/etc. does not automatically archive child records. Child visibility is handled by read queries where currently implemented.
- Nested operational endpoints generally use active context by default, but detailed archive semantics for every nested route are parked for now. We will revisit after higher-value MVP features are done.
- Site history and AI analysis should use active records by default, but deeper archive behavior for history/AI routes is also parked for now.
- `FindingAttachment` link rows are not archived. Links may be removed without deleting findings or attachments.
- Further archive edge cases are intentionally deferred until after the frontend, local AI model integration, and regulation comparison/versioning work are further along.
