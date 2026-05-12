# AI-integrated Compliance Database Tool

## IN PROGRESS!!!  USE AT YOUR OWN RISK!!!

[![CI](https://github.com/elliottbache/compliance/actions/workflows/ci.yaml/badge.svg)](https://github.com/elliottbache/compliance/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/github/elliottbache/compliance/graph/badge.svg?token=kNwbaexX4N)](https://codecov.io/github/elliottbache/compliance)
[![Release](https://img.shields.io/github/v/release/elliottbache/compliance)](https://github.com/elliottbache/compliance/releases)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm_NC_1.0.0-525252?style=flat-square)](https://polyformproject.org/licenses/noncommercial/1.0.0/)


## Short description
This project is a backend-first inspection and compliance management system designed to keep 
certification history, findings, rules, evidence, and site records organized in one place. 
Its goal is to improve traceability, make historical reviews easier, and support faster, more 
consistent report generation without replacing human technical judgment. Over time, it is 
intended to add tightly controlled AI assistance for tasks like summarization, drafting, and 
comparison of past certifications while keeping factual retrieval and validation in code.


## TODO
- Add local model option to use for site analysis.
- Add privacy for Anthropic and write guide in README.
- Add LLM function to return differences in regulation since last visit.
- Add stop_reason: "refusal" and stop_reason: "max_tokens" and others to requerying on failure in anthropic_api.py
- Add migration
- Add LLM to parse regulation into database.
- Add LLM to compare current regulation with last regulation
- Add MCP and hosting?

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
