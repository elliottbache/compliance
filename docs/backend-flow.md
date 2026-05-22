# Backend Code Flow

This note explains the normal backend flow through the FastAPI API layer,
service layer, persistence layer, and supporting helpers. It intentionally
describes the recurring patterns instead of providing an exact execution trace
for every endpoint.

## Entry Point

The backend application starts in `backend/src/compliance/api/main.py`.

`main.py` creates the `FastAPI` app, configures logging in the lifespan hook,
registers CORS middleware, and includes these routers:

- `sites.router`
- `certifications.router`
- `findings.router`
- `attachments.router`
- `clients.router`
- `certifiers.router`
- `rules.router`
- `regulations.router`

Each route receives a request-scoped SQLAlchemy session through
`SessionDep`, which is defined in `backend/src/compliance/api/deps.py` and
ultimately calls `compliance.db.db_access.get_db()`.

Typical setup flow:

```text
FastAPI route
-> SessionDep
-> get_db()
-> get_engine()
-> _build_db_url()
-> SQLAlchemy Session
```

## Endpoint Inventory

### Clients

Defined in `backend/src/compliance/api/routers/clients.py`.

| Method | Path | Route function | Primary service call |
| --- | --- | --- | --- |
| `GET` | `/clients` | `get_clients_route` | `get_clients` |
| `GET` | `/clients/{nif}` | `get_clients_by_nif_route` | `get_client_by_nif` |
| `GET` | `/clients/{nif}/sites` | `get_client_sites_route` | `get_client_by_nif`, then `get_sites` |
| `POST` | `/clients` | `post_new_client_route` | `post_new_client` |
| `POST` | `/clients/{nif}/archive` | `post_client_archived_by_nif_route` | `post_client_archived_by_nif` |
| `POST` | `/clients/{nif}/restore` | `post_client_restored_by_nif_route` | `post_client_restored_by_nif` |

### Sites

Defined in `backend/src/compliance/api/routers/sites.py`.

| Method | Path | Route function | Primary service call |
| --- | --- | --- | --- |
| `GET` | `/sites` | `get_sites_route` | `get_sites` |
| `GET` | `/sites/{site_id}` | `get_site_by_id_route` | `get_site_by_id` |
| `GET` | `/sites/{site_id}/attachments` | `get_site_attachments_route` | `get_site_attachments` |
| `GET` | `/sites/{site_id}/certifications` | `get_site_certifications_route` | `get_site_certifications`, then `format_site_certifications` |
| `GET` | `/sites/{site_id}/history` | `get_site_history_route` | `get_site_history` |
| `POST` | `/sites` | `post_new_site_route` | `post_new_site` |
| `POST` | `/sites/{site_id}/archive` | `post_site_archived_by_id_route` | `post_site_archived_by_id` |
| `POST` | `/sites/{site_id}/restore` | `post_site_restored_by_id_route` | `post_site_restored_by_id` |
| `POST` | `/sites/{site_id}/analysis` | `create_site_analysis_route` | `_create_site_analysis` |

### Certifiers

Defined in `backend/src/compliance/api/routers/certifiers.py`.

| Method | Path | Route function | Primary service call |
| --- | --- | --- | --- |
| `GET` | `/certifiers` | `get_certifiers_route` | `get_certifiers` |
| `GET` | `/certifiers/{certifier_id}` | `get_certifiers_by_id_route` | `get_certifier_by_id` |
| `POST` | `/certifiers` | `post_new_certifier_route` | `post_new_certifier` |
| `POST` | `/certifiers/{certifier_id}/archive` | `post_certifier_archived_by_id_route` | `post_certifier_archived_by_id` |
| `POST` | `/certifiers/{certifier_id}/restore` | `post_certifier_restored_by_id_route` | `post_certifier_restored_by_id` |

### Regulations

Defined in `backend/src/compliance/api/routers/regulations.py`.

| Method | Path | Route function | Primary service call |
| --- | --- | --- | --- |
| `GET` | `/regulations` | `get_regulations_route` | `get_regulations` |
| `GET` | `/regulations/{regulation_id}` | `get_regulation_by_id_route` | `get_regulation_by_id` |
| `POST` | `/regulations` | `post_new_regulation_route` | `post_new_regulation` |
| `POST` | `/regulations/{regulation_id}/archive` | `post_regulation_archived_by_id_route` | `post_regulation_archived_by_id` |
| `POST` | `/regulations/{regulation_id}/restore` | `post_regulation_restored_by_id_route` | `post_regulation_restored_by_id` |

### Rules

Defined in `backend/src/compliance/api/routers/rules.py`.

| Method | Path | Route function | Primary service call |
| --- | --- | --- | --- |
| `GET` | `/rules` | `get_rules_route` | `get_rules` |
| `GET` | `/rules/{rule_id}` | `get_rule_by_id_route` | `get_rule_by_id` |
| `POST` | `/rules` | `post_new_rule_route` | `post_new_rule` |
| `POST` | `/rules/{rule_id}/archive` | `post_rule_archived_by_id_route` | `post_rule_archived_by_id` |
| `POST` | `/rules/{rule_id}/restore` | `post_rule_restored_by_id_route` | `post_rule_restored_by_id` |

### Certifications

Defined in `backend/src/compliance/api/routers/certifications.py`.

| Method | Path | Route function | Primary service call |
| --- | --- | --- | --- |
| `GET` | `/certifications` | `get_certifications_route` | `get_certifications` |
| `GET` | `/certifications/{certification_id}` | `get_certification_by_id_route` | `get_certification_by_id` |
| `GET` | `/certifications/{certification_id}/attachments` | `get_certification_attachments_by_id_route` | `get_certification_attachments_by_id` |
| `GET` | `/certifications/{certification_id}/findings` | `get_certification_findings_route` | `get_certification_by_id`, then `get_findings` |
| `POST` | `/certifications` | `post_new_certification_route` | `post_new_certification` |
| `POST` | `/certifications/{certification_id}/archive` | `post_certification_archived_by_id_route` | `post_certification_archived_by_id` |
| `POST` | `/certifications/{certification_id}/restore` | `post_certification_restored_by_id_route` | `post_certification_restored_by_id` |

### Findings

Defined in `backend/src/compliance/api/routers/findings.py`.

| Method | Path | Route function | Primary service call |
| --- | --- | --- | --- |
| `GET` | `/findings` | `get_findings_route` | `get_findings` |
| `GET` | `/findings/{finding_id}` | `get_finding_by_id_route` | `get_finding_by_id` |
| `POST` | `/findings` | `post_new_finding_route` | `post_new_finding` |
| `POST` | `/findings/{finding_id}/archive` | `post_finding_archived_by_id_route` | `post_finding_archived_by_id` |
| `POST` | `/findings/{finding_id}/restore` | `post_finding_restored_by_id_route` | `post_finding_restored_by_id` |

### Attachments

Defined in `backend/src/compliance/api/routers/attachments.py`.

| Method | Path | Route function | Primary service call |
| --- | --- | --- | --- |
| `GET` | `/attachments` | `get_attachments_route` | `get_attachments` |
| `GET` | `/attachments/{attachment_id}` | `get_attachment_by_id_route` | `get_attachment_by_id` |
| `GET` | `/attachments/{attachment_id}/download` | `get_attachment_download_route` | `get_attachment_download` |
| `POST` | `/attachments` | `post_new_attachment_route` | `post_new_attachment` |
| `POST` | `/attachments/upload` | `post_attachment_upload_route` | `post_attachment_upload` |
| `POST` | `/attachments/{attachment_id}/archive` | `post_attachment_archived_by_id_route` | `post_attachment_archived_by_id` |
| `POST` | `/attachments/{attachment_id}/restore` | `post_attachment_restored_by_id_route` | `post_attachment_restored_by_id` |

## Typical Flow Patterns

### Service Call Map

Most route functions delegate to one same-domain service function. That service
function then normally calls a small set of shared helpers, SQLAlchemy session
methods, and formatter functions.

| Service area | Service functions | Functions they normally call |
| --- | --- | --- |
| Clients | `get_clients`, `get_client_by_nif`, `post_new_client`, `post_client_archived_by_nif`, `post_client_restored_by_nif` | `select`, `session.execute`, `session.get`, `record_is_visible`, `session.add`, `session.commit`, `session.rollback`, `get_constraint_name`, `archive_record_by_id`, `restore_record_by_id` |
| Sites CRUD | `get_sites`, `get_site_by_id`, `post_new_site`, `post_site_archived_by_id`, `post_site_restored_by_id` | `select`, `session.execute`, `session.get`, `record_is_visible`, `session.add`, `session.commit`, `session.rollback`, `get_constraint_name`, `archive_record_by_id`, `restore_record_by_id` |
| Site aggregates | `get_site_attachments`, `get_site_certifications`, `get_site_history`, `format_site_certifications` | `session.get`, `record_is_visible`, `select`, `session.execute`, `_format_site_attachments`, `format_attachment`, `_format_site_history`, `_build_finding_history_from_site_history` |
| Certifiers | `get_certifiers`, `get_certifier_by_id`, `post_new_certifier`, `post_certifier_archived_by_id`, `post_certifier_restored_by_id` | `select`, `session.execute`, `session.get`, `record_is_visible`, `session.add`, `session.commit`, `session.rollback`, `get_constraint_name`, `archive_record_by_id`, `restore_record_by_id` |
| Regulations | `get_regulations`, `get_regulation_by_id`, `post_new_regulation`, `post_regulation_archived_by_id`, `post_regulation_restored_by_id` | `select`, `session.execute`, `session.get`, `record_is_visible`, `session.add`, `session.commit`, `session.rollback`, `get_constraint_name`, `archive_record_by_id`, `restore_record_by_id` |
| Rules | `get_rules`, `get_rule_by_id`, `post_new_rule`, `post_rule_archived_by_id`, `post_rule_restored_by_id` | `select`, `session.execute`, `session.get`, `record_is_visible`, `session.add`, `session.commit`, `session.rollback`, `get_constraint_name`, `archive_record_by_id`, `restore_record_by_id` |
| Certifications | `get_certifications`, `get_certification_by_id`, `get_certification_attachments_by_id`, `post_new_certification`, `post_certification_archived_by_id`, `post_certification_restored_by_id` | `select`, `session.execute`, `session.get`, `record_is_visible`, `certification_parent_chain_is_visible`, `format_attachment`, `_format_certification_attachments`, `session.add`, `session.commit`, `session.rollback`, `get_constraint_name`, `archive_record_by_id`, `restore_record_by_id` |
| Findings | `get_findings`, `get_finding_by_id`, `post_new_finding`, `post_finding_archived_by_id`, `post_finding_restored_by_id` | `select`, `session.execute`, `session.get`, `record_is_visible`, `certification_parent_chain_is_visible`, `_format_findings`, `_build_finding_out`, `_build_finding_attachments`, `session.add`, `session.flush`, `session.commit`, `session.rollback`, `archive_record_by_id`, `restore_record_by_id` |
| Attachment metadata | `get_attachments`, `get_attachment_by_id`, `post_new_attachment`, `post_attachment_archived_by_id`, `post_attachment_restored_by_id` | `select`, `session.execute`, `session.get`, `record_is_visible`, `_format_attachments`, `_build_attachment_out`, `format_attachment`, `_format_new_attachment_with_context`, `session.add`, `session.flush`, `session.commit`, `session.rollback`, `archive_record_by_id`, `restore_record_by_id` |
| Attachment files | `post_attachment_upload`, `get_attachment_download` | `session.get`, `_validate_file_size_type_and_ext`, file-system read/write checks, `session.add`, `session.commit`, `session.refresh`, `session.rollback` |
| Site analysis | `_create_site_analysis`, `summarize_previous_visits` | `get_site_history`, `_mock_site_analysis`, `_build_site_analysis_system_prompt`, `_build_site_analysis_user_message`, `call_structured_model`, `validate_llm_references` |

### Read Endpoints

Read routes usually validate query and path parameters through FastAPI type
annotations, call one service function, translate service failures into
`HTTPException`, then return either service-layer Pydantic output or an API
schema model.

Typical flow:

```text
router function
-> service read function
-> optional parent/filter visibility checks with session.get(...)
-> record_is_visible(...)
-> SQLAlchemy select(...) query
-> session.execute(...)
-> optional formatter helper
-> API response model
```

The simple lookup services, such as `get_client_by_nif`,
`get_certifier_by_id`, and `get_regulation_by_id`, often use:

```text
service function
-> session.get(...)
-> record_is_visible(...)
-> ORM object or None
```

The richer aggregate reads, such as site history, findings, and attachments,
usually build explicit `select(...)` statements with joins and then pass
mapping rows into formatter helpers.

Examples:

- `get_site_history` calls `_format_site_history`, which calls
  `_build_finding_history_from_site_history` for finding rows.
- `get_site_attachments` calls `_format_site_attachments`, which groups rows
  by attachment and calls `format_attachment`.
- `get_certification_attachments_by_id` calls
  `_format_certification_attachments`, which also calls `format_attachment`.
- `get_findings` calls `_format_findings`, which calls `_build_finding_out`
  and `_build_finding_attachments`.
- `get_attachments` calls `_format_attachments`, which calls
  `_build_attachment_out`.
- `get_attachment_by_id` calls `format_attachment`, which may call
  `_build_finding_history_from_site_attachments`.

### Create Endpoints

Create routes accept API request schemas, call a service create function, catch
domain-specific exceptions, and return the created object through an output
schema.

Typical flow:

```text
router function
-> service create function
-> validate required parent records with session.get(...)
-> construct ORM model
-> session.add(...)
-> session.flush(...) when generated IDs are needed before related rows
-> create link rows when needed
-> optional formatter helper for response context
-> session.commit()
-> output schema
```

On integrity failures, create services call `session.rollback()`. The simpler
create services also call `get_constraint_name(...)` to map database
constraint names to specific service exceptions.

Examples:

- `post_new_client`, `post_new_certifier`, `post_new_regulation`,
  `post_new_rule`, `post_new_site`, and `post_new_certification` create one
  main ORM record and map database conflicts into domain-specific errors.
- `post_new_finding` validates its certification, rule, and optional
  attachment links, creates `Finding`, creates `FindingAttachment` link rows,
  then formats the returned finding with joined context.
- `post_new_attachment` validates its certification and optional finding
  links, creates `Attachment`, creates `FindingAttachment` link rows, then
  calls `_format_new_attachment_with_context`.

### Archive And Restore Endpoints

Archive and restore routes are intentionally thin. The per-domain service
function normally delegates to a shared lifecycle helper.

Typical archive flow:

```text
router archive function
-> post_*_archived_by_* service function
-> archive_record_by_id(...)
-> session.get(...)
-> set archived_at and archive_reason when needed
-> session.commit()
-> return archived record
```

Typical restore flow:

```text
router restore function
-> post_*_restored_by_* service function
-> restore_record_by_id(...)
-> session.get(...)
-> clear archived_at and archive_reason when needed
-> session.commit()
-> return restored record
```

Most archive and restore services return the ORM record directly. Attachment
and finding archive/restore functions do one extra read after the lifecycle
update so the route can return the same contextual response shape as the detail
endpoints.

### Attachment File Endpoints

Attachment metadata and file content are separate workflows.

Metadata creation:

```text
POST /attachments
-> post_new_attachment
-> validate certification and finding links
-> create Attachment metadata with no file_path or uploaded_at
-> create FindingAttachment link rows
-> commit
```

File upload:

```text
POST /attachments/upload
-> post_attachment_upload
-> session.get(Attachment, attachment_id)
-> _validate_file_size_type_and_ext(...)
-> write file under backend storage
-> update file_path, file_name, and uploaded_at
-> session.commit()
```

File download:

```text
GET /attachments/{attachment_id}/download
-> get_attachment_download
-> session.get(Attachment, attachment_id)
-> validate file_path exists on disk
-> FileResponse
```

### Site Analysis Endpoint

The AI-backed site analysis endpoint is a small orchestration layer around the
normal site-history read path.

Typical flow:

```text
POST /sites/{site_id}/analysis
-> _create_site_analysis
-> get_site_history
-> summarize_previous_visits
-> _mock_site_analysis when AI_MODE=mock
   or
   _build_site_analysis_system_prompt
   -> _build_site_analysis_user_message
   -> call_structured_model when AI_MODE=anthropic
-> validate_llm_references
-> SiteAnalysis response
```

The route translates Anthropic API errors, JSON parsing errors, Pydantic
validation errors, and invalid evidence references into `502` responses.

## Cross-Cutting Rules

- The API layer owns HTTP-specific concerns: path/query/body parsing, response
  status codes, and `HTTPException` mapping.
- The service layer owns business checks, archive visibility, SQLAlchemy
  queries, commits, rollbacks, and response-shaping helpers.
- `include_archived` defaults to `false` for list and aggregate endpoints, but
  many exact detail endpoints default to `true` so archived records can still
  be inspected directly.
- Archive visibility is centralized through `record_is_visible(...)` for simple
  parent checks and through explicit `archived_at.is_(None)` filters in joined
  queries.
- Shared archive and restore mutations are centralized in
  `archive_record_by_id(...)` and `restore_record_by_id(...)`.
- API schemas live in `backend/src/compliance/api/schemas.py`; service-layer
  output schemas live in `backend/src/compliance/services/schemas.py` and
  `backend/src/compliance/schemas.py`.
