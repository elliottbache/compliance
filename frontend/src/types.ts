export type LoadingState = string | null;

export type ApiErrorMessage = string | null;

export type ApiStatusCode = number;

export type ApiErrorBody = {
  detail?: unknown;
};

export type ArchivedFields = {
  archived_at: string | null;
  archive_reason: string | null;
};

export type FindingHistory = {
  finding_id: number;
  finding: string;
  rule_index: string;
  rule_title: string | null;
  rule_description: string;
};

export type CertificationHistory = {
  cert_id: number;
  result: "Pass" | "Fail" | null;
  resolution_date: string | null;
  reg_title: string;
  reg_description: string;
  certifier_org_name: string;
  inspection_date: string | null;
  findings: FindingHistory[];
};

export type SiteHistory = {
  site_id: number;
  certifications: CertificationHistory[];
  inspection_count: number;
  latest_inspection_date: string | null;
};

export type FindingLink = {
  finding_id: number;
  finding: string;
  rule_index: string;
  rule_title: string | null;
  rule_description: string;
};

export type AttachmentWithContextOut = ArchivedFields & {
  id: number;
  file_name: string | null;
  file_path: string;
  description: string | null;
  uploaded_at: string;

  certification_id: number;
  inspection_date: string | null;
  regulation_id: number;
  regulation_title: string;

  finding_links: FindingLink[];
};

export type SiteAttachmentsOut = {
  site_id: number;
  attachments: AttachmentWithContextOut[];
};

export type EvidenceRef = {
  cert_id: number;
  reg_title: string;
  inspection_date?: string | null;
  finding_id?: number | null;
  rule_index?: string | null;
  support_text: string;
};

export type SiteAnalysisListItem = {
  item: string;
  evidence: EvidenceRef[];
  confidence_note?: string | null;
  why_missing_matters?: string | null;
  basis?: string | null;
  [key: string]: unknown;
};

export type SiteAnalysis = {
  site_id?: number;
  executive_summary?: string | null;
  recurring_issues?: SiteAnalysisListItem[] | null;
  missing_information?: SiteAnalysisListItem[] | null;
  needs_human_review?: SiteAnalysisListItem[] | null;
  suggestions?: SiteAnalysisListItem[] | null;
  [key: string]: unknown;
};

export type AdminSection =
  | "sites"
  | "clients"
  | "certifiers"
  | "regulations"
  | "rules"
  | "certifications"
  | "findings"
  | "attachments";

export type ArchiveRequest = {
  archive_reason?: string | null;
};

export type ClientRecord = ArchivedFields & {
  nif: string;
  company_name: string;
  contact_name: string | null;
  email: string | null;
  telephone: string | null;
};

export type SiteRecord = ArchivedFields & {
  id: number;
  client_nif: string;
  city: string;
  postal_code: string;
  street: string;
  street_number: string;
  suite: string | null;
  address_info: string | null;
};

export type CertifierRecord = ArchivedFields & {
  id: number;
  organization_name: string;
};

export type RegulationRecord = ArchivedFields & {
  id: number;
  title: string;
  description: string;
  published_date: string;
};

export type RuleRecord = ArchivedFields & {
  id: number;
  regulation_id: number;
  rule_index: string;
  title: string | null;
  description: string;
};

export type CertificationRecord = ArchivedFields & {
  id: number;
  site_id: number;
  certifier_id: number;
  regulation_id: number;
  result: "Pass" | "Fail" | null;
  inspection_date: string | null;
  resolution_date: string | null;
};

export type FindingRecord = ArchivedFields & {
  finding_id: number;
  certification_id: number;
  rule_id: number;
  finding: string;
};

export type AttachmentRecord = ArchivedFields & {
  id: number;
  certification_id: number;
  file_path?: string;
  file_name?: string | null;
  description: string | null;
  uploaded_at: string | null;
};

export type AdminRecord =
  | ClientRecord
  | SiteRecord
  | CertifierRecord
  | RegulationRecord
  | RuleRecord
  | CertificationRecord
  | FindingRecord
  | AttachmentRecord;
