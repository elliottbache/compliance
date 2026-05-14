import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  ADMIN_RESOURCE_PATHS,
  archiveAdminRecord,
  createAdminRecord,
  listAdminRecords,
  restoreAdminRecord,
} from "../../api/complianceApi";
import type { FindingRecord } from "../../types";
import {
  formatArchivedAt,
  formatArchiveReason,
} from "../../utils/adminFormatters";
import { getErrorMessage } from "../../utils/apiErrors";

type FindingCreatePayload = {
  certification_id: number;
  rule_id: number;
  finding: string;
  attachment_ids?: number[];
};

type FindingFormState = {
  certification_id: string;
  rule_id: string;
  finding: string;
  attachment_ids: string;
};

const EMPTY_FORM: FindingFormState = {
  certification_id: "",
  rule_id: "",
  finding: "",
  attachment_ids: "",
};

const FINDINGS_PATH = ADMIN_RESOURCE_PATHS.findings;

function isArchived(finding: FindingRecord): boolean {
  return finding.archived_at !== null;
}

function getFindingId(finding: FindingRecord): number {
  return finding.finding_id;
}

function parseIdList(value: string): number[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map(Number)
    .filter((item) => Number.isInteger(item) && item > 0);
}

function buildCreatePayload(form: FindingFormState): FindingCreatePayload {
  const attachmentIds = parseIdList(form.attachment_ids);

  return {
    certification_id: Number(form.certification_id),
    rule_id: Number(form.rule_id),
    finding: form.finding.trim(),
    ...(attachmentIds.length > 0 ? { attachment_ids: attachmentIds } : {}),
  };
}

export function FindingsSection() {
  const [findings, setFindings] = useState<FindingRecord[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState<FindingFormState>(EMPTY_FORM);
  const [archiveReasons, setArchiveReasons] = useState<Record<number, string>>(
    {},
  );
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadFindings = useCallback(async () => {
    try {
      setLoading("Loading findings...");
      setError(null);
      const loadedFindings = await listAdminRecords<FindingRecord>(
        FINDINGS_PATH,
        { includeArchived },
      );
      setFindings(loadedFindings);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }, [includeArchived]);

  useEffect(() => {
    void loadFindings();
  }, [loadFindings]);

  function updateFormField(field: keyof FindingFormState, value: string): void {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: value,
    }));
  }

  function updateArchiveReason(findingId: number, value: string): void {
    setArchiveReasons((currentReasons) => ({
      ...currentReasons,
      [findingId]: value,
    }));
  }

  async function handleCreateFinding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading("Creating finding...");
      setError(null);
      await createAdminRecord<FindingCreatePayload, FindingRecord>(
        FINDINGS_PATH,
        buildCreatePayload(form),
      );
      setForm(EMPTY_FORM);
      setShowCreateForm(false);
      await loadFindings();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleArchiveFinding(findingId: number) {
    try {
      setLoading(`Archiving finding ${findingId}...`);
      setError(null);
      await archiveAdminRecord<FindingRecord>(
        FINDINGS_PATH,
        findingId,
        archiveReasons[findingId],
      );
      updateArchiveReason(findingId, "");
      await loadFindings();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleRestoreFinding(findingId: number) {
    try {
      setLoading(`Restoring finding ${findingId}...`);
      setError(null);
      await restoreAdminRecord<FindingRecord>(FINDINGS_PATH, findingId);
      await loadFindings();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  const isBusy = loading !== null;

  return (
    <section className="admin-record-section">
      <div className="admin-record-header">
        <div>
          <h3>Findings</h3>
          <p>List, create, archive, and restore inspection findings.</p>
        </div>

        <div className="admin-actions">
          <label className="checkbox-label">
            <input
              checked={includeArchived}
              type="checkbox"
              onChange={(event) => setIncludeArchived(event.target.checked)}
            />
            Include archived
          </label>

          <button
            className="button"
            disabled={isBusy}
            type="button"
            onClick={() => void loadFindings()}
          >
            Refresh
          </button>

          <button
            className="button button-primary"
            disabled={isBusy}
            type="button"
            onClick={() => setShowCreateForm((current) => !current)}
          >
            {showCreateForm ? "Cancel" : "Add Finding"}
          </button>
        </div>
      </div>

      {loading ? <p className="loading-text">{loading}</p> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {showCreateForm ? (
        <form className="admin-form" onSubmit={handleCreateFinding}>
          <div className="form-grid">
            <label>
              Certification ID
              <input
                required
                className="input"
                min="1"
                type="number"
                value={form.certification_id}
                onChange={(event) =>
                  updateFormField("certification_id", event.target.value)
                }
              />
            </label>

            <label>
              Rule ID
              <input
                required
                className="input"
                min="1"
                type="number"
                value={form.rule_id}
                onChange={(event) =>
                  updateFormField("rule_id", event.target.value)
                }
              />
            </label>

            <label className="form-grid-wide">
              Finding
              <textarea
                required
                className="textarea admin-textarea"
                value={form.finding}
                onChange={(event) =>
                  updateFormField("finding", event.target.value)
                }
              />
            </label>

            <label className="form-grid-wide">
              Attachment IDs, optional comma-separated
              <input
                className="input"
                placeholder="Example: 3, 8, 12"
                value={form.attachment_ids}
                onChange={(event) =>
                  updateFormField("attachment_ids", event.target.value)
                }
              />
            </label>
          </div>

          <div className="button-row">
            <button
              className="button button-primary"
              disabled={isBusy}
              type="submit"
            >
              Create
            </button>

            <button
              className="button"
              disabled={isBusy}
              type="button"
              onClick={() => {
                setForm(EMPTY_FORM);
                setShowCreateForm(false);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      <div className="table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Certification ID</th>
              <th>Rule ID</th>
              <th>Finding</th>
              <th>Archived at</th>
              <th>Archive reason</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {findings.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={7}>
                  No findings found.
                </td>
              </tr>
            ) : (
              findings.map((finding) => (
                <tr
                  className={isArchived(finding) ? "archived-row" : ""}
                  key={getFindingId(finding)}
                >
                  <td>{getFindingId(finding)}</td>
                  <td>{finding.certification_id}</td>
                  <td>{finding.rule_id}</td>
                  <td>{finding.finding}</td>
                  <td>
                    {isArchived(finding) ? (
                      <span className="badge badge-archived">
                        {formatArchivedAt(finding.archived_at)}
                      </span>
                    ) : (
                      <span className="badge badge-active">Active</span>
                    )}
                  </td>
                  <td>{formatArchiveReason(finding.archive_reason)}</td>
                  <td>
                    {isArchived(finding) ? (
                      <button
                        className="button"
                        disabled={isBusy}
                        type="button"
                        onClick={() => void handleRestoreFinding(getFindingId(finding))}
                      >
                        Restore
                      </button>
                    ) : (
                      <div className="row-actions">
                        <input
                          className="input archive-input"
                          placeholder="Optional reason"
                          value={archiveReasons[getFindingId(finding)] ?? ""}
                          onChange={(event) =>
                            updateArchiveReason(getFindingId(finding), event.target.value)
                          }
                        />

                        <button
                          className="button"
                          disabled={isBusy}
                          type="button"
                          onClick={() => void handleArchiveFinding(getFindingId(finding))}
                        >
                          Archive
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
