-- Demo seed data for the compliance MVP.
--
-- Intended use:
--   1. Run Alembic migrations first so the schema exists.
--   2. Run this script against a local/demo database only.
--   3. Add the demo files listed below under backend/storage/attachments/.
--
-- This script intentionally does not insert into alembic_version.
-- It also clears existing domain data so it can be re-run locally.
--
-- Demo files expected by attachment rows:
--   backend/storage/attachments/demo-data-encryption-audit.pdf
--   backend/storage/attachments/demo-server-room-access-photo.jpg
--   backend/storage/attachments/demo-retention-policy-review.pdf
--   backend/storage/attachments/demo-ai-bias-audit-summary.pdf
--   backend/storage/attachments/demo-remediation-plan.pdf
--   backend/storage/attachments/demo-transfer-register-gap.pdf

BEGIN;

TRUNCATE TABLE
    public.finding_attachments,
    public.findings,
    public.attachments,
    public.certifications,
    public.rules,
    public.sites,
    public.regulations,
    public.certifiers,
    public.clients
RESTART IDENTITY CASCADE;

-- Certifiers
INSERT INTO public.certifiers (id, organization_name, archived_at, archive_reason)
VALUES
    (1, 'Iberian Compliance Auditors', NULL, NULL),
    (2, 'Mediterranean Safety Review', NULL, NULL),
    (3, 'Demo Certification Bureau', NULL, NULL);

-- Clients
INSERT INTO public.clients (
    nif,
    company_name,
    contact_name,
    email,
    telephone,
    archived_at,
    archive_reason
)
VALUES
    (
        'B46123456',
        'Demo Logistics S.L.',
        'Elena Martin',
        'compliance@example.com',
        963123456,
        NULL,
        NULL
    ),
    (
        'A28987654',
        'Example Solar Operations S.A.',
        'Marco Silva',
        'operations@example.test',
        912987654,
        NULL,
        NULL
    );

-- Regulations
INSERT INTO public.regulations (
    id,
    title,
    description,
    published_date,
    archived_at,
    archive_reason
)
VALUES
    (
        11,
        'Global Data Privacy Framework',
        'Demo standard covering personal-data encryption, transfer controls, consent, retention, and evidence requirements.',
        '2024-05-12',
        NULL,
        NULL
    ),
    (
        12,
        'AI Safety Review Standard',
        'Demo standard covering AI risk assessment, bias review, explainability, and human oversight.',
        '2025-11-30',
        NULL,
        NULL
    );

-- Sites
INSERT INTO public.sites (
    id,
    nif,
    city,
    postal_code,
    street,
    street_number,
    suite,
    address_info,
    archived_at,
    archive_reason
)
VALUES
    (
        71,
        'B46123456',
        'Madrid',
        46003,
        'Calle de la Paz',
        9,
        'A',
        'Primary demo site for inspection-history and AI-analysis workflow.',
        NULL,
        NULL
    ),
    (
        72,
        'A28987654',
        'Valencia',
        46021,
        'Avenida del Puerto',
        42,
        NULL,
        'Secondary site included to make list/admin views less empty.',
        NULL,
        NULL
    );

-- Rules
INSERT INTO public.rules (
    id,
    regulation_id,
    rule_index,
    title,
    description,
    archived_at,
    archive_reason
)
VALUES
    (
        1,
        11,
        '1.1',
        'Data encryption standard',
        'Personal data must be encrypted at rest and in transit using approved cryptographic controls.',
        NULL,
        NULL
    ),
    (
        2,
        11,
        '1.2',
        'Cross-border transfer register',
        'Transfers of personal data outside the approved region must be documented with supporting contractual safeguards.',
        NULL,
        NULL
    ),
    (
        3,
        11,
        '1.3',
        'Retention review',
        'Retention periods must be documented, reviewed, and enforced through operational procedures.',
        NULL,
        NULL
    ),
    (
        4,
        12,
        '2.1',
        'AI bias review',
        'High-impact AI systems must have periodic bias review evidence and documented mitigation actions.',
        NULL,
        NULL
    ),
    (
        5,
        12,
        '2.2',
        'Human oversight',
        'Automated recommendations must remain subject to human review before operational or compliance decisions.',
        NULL,
        NULL
    );

-- Certifications / inspection events
INSERT INTO public.certifications (
    id,
    certifier_id,
    regulation_id,
    site_id,
    result,
    inspection_date,
    resolution_date,
    archived_at,
    archive_reason
)
VALUES
    (
        32,
        1,
        11,
        71,
        'Pass',
        '2025-10-15',
        '2025-11-01',
        NULL,
        NULL
    ),
    (
        33,
        2,
        12,
        71,
        'Pass',
        '2026-01-10',
        '2026-01-20',
        NULL,
        NULL
    ),
    (
        53,
        1,
        11,
        71,
        'Fail',
        '2026-05-03',
        '2026-05-06',
        NULL,
        NULL
    ),
    (
        54,
        3,
        11,
        72,
        NULL,
        '2026-05-10',
        NULL,
        NULL,
        NULL
    );

-- Attachments
-- file_name is the display name without extension.
INSERT INTO public.attachments (
    id,
    certification_id,
    file_path,
    description,
    uploaded_at,
    archived_at,
    archive_reason,
    file_name
)
VALUES
    (
        16,
        32,
        'backend/storage/attachments/demo-data-encryption-audit.pdf',
        'Audit report confirming encryption controls for the 2025 privacy inspection.',
        '2025-11-02 10:00:00+01',
        NULL,
        NULL,
        'data_encryption_audit'
    ),
    (
        17,
        32,
        'backend/storage/attachments/demo-server-room-access-photo.jpg',
        'Site visit photo showing restricted access controls for the server room.',
        '2025-11-02 10:15:00+01',
        NULL,
        NULL,
        'server_room_access_photo'
    ),
    (
        18,
        32,
        'backend/storage/attachments/demo-retention-policy-review.pdf',
        'Retention policy review notes identifying manual cleanup procedures.',
        '2025-11-02 10:30:00+01',
        NULL,
        NULL,
        'retention_policy_review'
    ),
    (
        19,
        33,
        'backend/storage/attachments/demo-ai-bias-audit-summary.pdf',
        'Summary of the AI bias review and human oversight checks.',
        '2026-01-21 09:30:00+01',
        NULL,
        NULL,
        'ai_bias_audit_summary'
    ),
    (
        21,
        53,
        'backend/storage/attachments/demo-remediation-plan.pdf',
        'Remediation plan prepared after the failed May 2026 privacy inspection.',
        '2026-05-06 14:00:00+02',
        NULL,
        NULL,
        'remediation_plan'
    ),
    (
        22,
        53,
        'backend/storage/attachments/demo-transfer-register-gap.pdf',
        'Evidence packet documenting missing transfer-register entries.',
        '2026-05-06 14:20:00+02',
        NULL,
        NULL,
        'transfer_register_gap'
    );

-- Findings
INSERT INTO public.findings (
    id,
    certification_id,
    rule_id,
    finding,
    archived_at,
    archive_reason
)
VALUES
    (
        13,
        32,
        1,
        'Encryption controls were verified for the production database and document archive.',
        NULL,
        NULL
    ),
    (
        14,
        32,
        3,
        'Retention policy exists, but the cleanup process still depends on a monthly manual checklist.',
        NULL,
        NULL
    ),
    (
        15,
        33,
        4,
        'AI bias review evidence was available and included mitigation notes for the latest model update.',
        NULL,
        NULL
    ),
    (
        16,
        33,
        5,
        'Human review is documented before AI recommendations are used in operational decisions.',
        NULL,
        NULL
    ),
    (
        21,
        53,
        2,
        'Transfer-register entries were incomplete for two external processors at the time of inspection.',
        NULL,
        NULL
    ),
    (
        22,
        53,
        3,
        'Manual retention cleanup remained unresolved and lacked evidence of completion for April 2026.',
        NULL,
        NULL
    );

-- Finding/attachment links
INSERT INTO public.finding_attachments (finding_id, attachment_id, certification_id)
VALUES
    (13, 16, 32),
    (13, 17, 32),
    (14, 18, 32),
    (15, 19, 33),
    (16, 19, 33),
    (21, 21, 53),
    (21, 22, 53),
    (22, 21, 53);

-- Sequence values
SELECT pg_catalog.setval('public.attachments_id_seq', 22, true);
SELECT pg_catalog.setval('public.certifications_id_seq', 54, true);
SELECT pg_catalog.setval('public.certifiers_id_seq', 3, true);
SELECT pg_catalog.setval('public.findings_id_seq', 22, true);
SELECT pg_catalog.setval('public.regulations_id_seq', 12, true);
SELECT pg_catalog.setval('public.rules_id_seq', 5, true);
SELECT pg_catalog.setval('public.sites_id_seq', 72, true);

COMMIT;
