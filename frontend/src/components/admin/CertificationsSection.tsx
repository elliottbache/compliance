import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  ADMIN_RESOURCE_PATHS,
  archiveAdminRecord,
  createAdminRecord,
  listAdminRecords,
  restoreAdminRecord,
} from "../../api/complianceApi";
import type { CertificationRecord } from "../../types";
import {
  formatArchivedAt,
  formatArchiveReason,
} from "../../utils/adminFormatters";
import { getErrorMessage } from "../../utils/apiErrors";

type CertificationCreatePayload = {
  site_id: number;
  certifier_id: number;
  regulation_id: number;
  inspector_id: number | null;
  result: "Pass" | "Fail" | null;
  inspection_date: string | null;
  resolution_date: string | null;
};

type CertificationFormState = {
  site_id: string;
  certifier_id: string;
  regulation_id: string;
  inspector_id: string;
  result: "" | "Pass" | "Fail";
  inspection_date: string;
  resolution_date: string;
};

const EMPTY_FORM: CertificationFormState = {
  site_id: "",
  certifier_id: "",
  regulation_id: "",
  inspector_id: "",
  result: "",
  inspection_date: "",
  resolution_date: "",
};

const CERTIFICATIONS_PATH = ADMIN_RESOURCE_PATHS.certifications;

function isArchived(certification: CertificationRecord): boolean {
  return certification.archived_at !== null;
}

function buildCreatePayload(
  form: CertificationFormState,
): CertificationCreatePayload {
  return {
    site_id: Number(form.site_id),
    certifier_id: Number(form.certifier_id),
    regulation_id: Number(form.regulation_id),
    inspector_id: form.inspector_id ? Number(form.inspector_id) : null,
    result: form.result || null,
    inspection_date: form.inspection_date || null,
    resolution_date: form.resolution_date || null,
  };
}

function formatDate(value: string | null): string {
  return value ?? "—";
}

export function CertificationsSection() {
  const [certifications, setCertifications] = useState<CertificationRecord[]>(
    [],
  );
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState<CertificationFormState>(EMPTY_FORM);
  const [archiveReasons, setArchiveReasons] = useState<Record<number, string>>(
    {},
  );
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadCertifications = useCallback(async () => {
    try {
      setLoading("Loading certifications...");
      setError(null);
      const loadedCertifications =
        await listAdminRecords<CertificationRecord>(CERTIFICATIONS_PATH, {
          includeArchived,
        });
      setCertifications(loadedCertifications);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }, [includeArchived]);

  useEffect(() => {
    void loadCertifications();
  }, [loadCertifications]);

  function updateFormField(
    field: keyof CertificationFormState,
    value: string,
  ): void {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: value,
    }));
  }

  function updateArchiveReason(certificationId: number, value: string): void {
    setArchiveReasons((currentReasons) => ({
      ...currentReasons,
      [certificationId]: value,
    }));
  }

  async function handleCreateCertification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading("Creating certification...");
      setError(null);
      await createAdminRecord<
        CertificationCreatePayload,
        CertificationRecord
      >(CERTIFICATIONS_PATH, buildCreatePayload(form));
      setForm(EMPTY_FORM);
      setShowCreateForm(false);
      await loadCertifications();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleArchiveCertification(certificationId: number) {
    try {
      setLoading(`Archiving certification ${certificationId}...`);
      setError(null);
      await archiveAdminRecord<CertificationRecord>(
        CERTIFICATIONS_PATH,
        certificationId,
        archiveReasons[certificationId],
      );
      updateArchiveReason(certificationId, "");
      await loadCertifications();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleRestoreCertification(certificationId: number) {
    try {
      setLoading(`Restoring certification ${certificationId}...`);
      setError(null);
      await restoreAdminRecord<CertificationRecord>(
        CERTIFICATIONS_PATH,
        certificationId,
      );
      await loadCertifications();
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
          <h3>Certifications</h3>
          <p>List, create, archive, and restore inspection events.</p>
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
            onClick={() => void loadCertifications()}
          >
            Refresh
          </button>

          <button
            className="button button-primary"
            disabled={isBusy}
            type="button"
            onClick={() => setShowCreateForm((current) => !current)}
          >
            {showCreateForm ? "Cancel" : "Add Certification"}
          </button>
        </div>
      </div>

      {loading ? <p className="loading-text">{loading}</p> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {showCreateForm ? (
        <form className="admin-form" onSubmit={handleCreateCertification}>
          <div className="form-grid">
            <label>
              Site ID
              <input
                required
                className="input"
                min="1"
                type="number"
                value={form.site_id}
                onChange={(event) =>
                  updateFormField("site_id", event.target.value)
                }
              />
            </label>

            <label>
              Certifier ID
              <input
                required
                className="input"
                min="1"
                type="number"
                value={form.certifier_id}
                onChange={(event) =>
                  updateFormField("certifier_id", event.target.value)
                }
              />
            </label>

            <label>
              Regulation ID
              <input
                required
                className="input"
                min="1"
                type="number"
                value={form.regulation_id}
                onChange={(event) =>
                  updateFormField("regulation_id", event.target.value)
                }
              />
            </label>

            <label>
              Inspector ID
              <input
                className="input"
                min="1"
                type="number"
                value={form.inspector_id}
                onChange={(event) =>
                  updateFormField("inspector_id", event.target.value)
                }
              />
            </label>

            <label>
              Result
              <select
                className="select"
                value={form.result}
                onChange={(event) =>
                  updateFormField("result", event.target.value)
                }
              >
                <option value="">Pending / unknown</option>
                <option value="Pass">Pass</option>
                <option value="Fail">Fail</option>
              </select>
            </label>

            <label>
              Inspection date
              <input
                className="input"
                type="date"
                value={form.inspection_date}
                onChange={(event) =>
                  updateFormField("inspection_date", event.target.value)
                }
              />
            </label>

            <label>
              Resolution date
              <input
                className="input"
                type="date"
                value={form.resolution_date}
                onChange={(event) =>
                  updateFormField("resolution_date", event.target.value)
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
              <th>Site ID</th>
              <th>Certifier ID</th>
              <th>Regulation ID</th>
              <th>Inspector ID</th>
              <th>Result</th>
              <th>Inspection date</th>
              <th>Resolution date</th>
              <th>Archived at</th>
              <th>Archive reason</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {certifications.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={11}>
                  No certifications found.
                </td>
              </tr>
            ) : (
              certifications.map((certification) => (
                <tr
                  className={isArchived(certification) ? "archived-row" : ""}
                  key={certification.id}
                >
                  <td>{certification.id}</td>
                  <td>{certification.site_id}</td>
                  <td>{certification.certifier_id}</td>
                  <td>{certification.regulation_id}</td>
                  <td>{certification.inspector_id ?? "—"}</td>
                  <td>{certification.result ?? "Pending"}</td>
                  <td>{formatDate(certification.inspection_date)}</td>
                  <td>{formatDate(certification.resolution_date)}</td>
                  <td>
                    {isArchived(certification) ? (
                      <span className="badge badge-archived">
                        {formatArchivedAt(certification.archived_at)}
                      </span>
                    ) : (
                      <span className="badge badge-active">Active</span>
                    )}
                  </td>
                  <td>{formatArchiveReason(certification.archive_reason)}</td>
                  <td>
                    {isArchived(certification) ? (
                      <button
                        className="button"
                        disabled={isBusy}
                        type="button"
                        onClick={() =>
                          void handleRestoreCertification(certification.id)
                        }
                      >
                        Restore
                      </button>
                    ) : (
                      <div className="row-actions">
                        <input
                          className="input archive-input"
                          placeholder="Optional reason"
                          value={archiveReasons[certification.id] ?? ""}
                          onChange={(event) =>
                            updateArchiveReason(
                              certification.id,
                              event.target.value,
                            )
                          }
                        />

                        <button
                          className="button"
                          disabled={isBusy}
                          type="button"
                          onClick={() =>
                            void handleArchiveCertification(certification.id)
                          }
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
