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
- Add function to return differences in regulation since last visit.
- Add stop_reason: "refusal" and stop_reason: "max_tokens" and others to requerying on failure in anthropic_api.py
- Add migration
- Add LLM to parse regulation into database.
- Add LLM to compare current regulation with last regulation

## Database description
### Notes
- Historical records are not hard-deleted by normal users.
- Important records are archived or deletion-restricted.
- Link rows may be deleted/unlinked where safe.
- Finding-attachment links are managed through finding and attachment creation endpoints. Standalone link CRUD is deferred until there is a real UX need.