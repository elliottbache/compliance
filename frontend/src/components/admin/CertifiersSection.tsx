import { useCallback, useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import {
  ADMIN_RESOURCE_PATHS,
  archiveAdminRecord,
  createAdminRecord,
  listAdminRecords,
  restoreAdminRecord,
} from "../../api/complianceApi";
import type { CertifierRecord } from "../../types";
import { getErrorMessage } from "../../utils/apiErrors";

type CertifierCreatePayload = {
  organization_name: string;
};

type CertifierFormState = {
  organization_name: string;
};

const EMPTY_FORM: CertifierFormState = {
  organization_name: "",
};

const CERTIFIERS_PATH = ADMIN_RESOURCE_PATHS.certifiers;

function isArchived(certifier: CertifierRecord): boolean {
  return certifier.archived_at !== null;
}

function buildCreatePayload(form: CertifierFormState): CertifierCreatePayload {
  return {
    organization_name: form.organization_name.trim(),
  };
}

function formatDate(value: string | null): string {
  return value ?? "—";
}

export function CertifiersSection() {
  const [certifiers, setCertifiers] = useState<CertifierRecord[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState<CertifierFormState>(EMPTY_FORM);
  const [archiveReasons, setArchiveReasons] = useState<Record<number, string>>(
    {},
  );
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadCertifiers = useCallback(async () => {
    try {
      setLoading("Loading certifiers...");
      setError(null);
      const loadedCertifiers = await listAdminRecords<CertifierRecord>(
        CERTIFIERS_PATH,
        { includeArchived },
      );
      setCertifiers(loadedCertifiers);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }, [includeArchived]);

  useEffect(() => {
    void loadCertifiers();
  }, [loadCertifiers]);

  function updateFormField(
    field: keyof CertifierFormState,
    event: ChangeEvent<HTMLInputElement>,
  ): void {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: event.target.value,
    }));
  }

  function updateArchiveReason(certifierId: number, value: string): void {
    setArchiveReasons((currentReasons) => ({
      ...currentReasons,
      [certifierId]: value,
    }));
  }

  async function handleCreateCertifier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading("Creating certifier...");
      setError(null);
      await createAdminRecord<CertifierCreatePayload, CertifierRecord>(
        CERTIFIERS_PATH,
        buildCreatePayload(form),
      );
      setForm(EMPTY_FORM);
      setShowCreateForm(false);
      await loadCertifiers();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleArchiveCertifier(certifierId: number) {
    try {
      setLoading(`Archiving certifier ${certifierId}...`);
      setError(null);
      await archiveAdminRecord<CertifierRecord>(
        CERTIFIERS_PATH,
        certifierId,
        archiveReasons[certifierId],
      );
      updateArchiveReason(certifierId, "");
      await loadCertifiers();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleRestoreCertifier(certifierId: number) {
    try {
      setLoading(`Restoring certifier ${certifierId}...`);
      setError(null);
      await restoreAdminRecord<CertifierRecord>(CERTIFIERS_PATH, certifierId);
      await loadCertifiers();
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
          <h3>Certifiers</h3>
          <p>List, create, archive, and restore certifying organizations.</p>
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
            onClick={() => void loadCertifiers()}
          >
            Refresh
          </button>

          <button
            className="button button-primary"
            disabled={isBusy}
            type="button"
            onClick={() => setShowCreateForm((current) => !current)}
          >
            {showCreateForm ? "Cancel" : "Add Certifier"}
          </button>
        </div>
      </div>

      {loading ? <p className="loading-text">{loading}</p> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {showCreateForm ? (
        <form className="admin-form" onSubmit={handleCreateCertifier}>
          <div className="form-grid">
            <label>
              Organization name
              <input
                required
                className="input"
                value={form.organization_name}
                onChange={(event) => updateFormField("organization_name", event)}
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
              <th>Organization name</th>
              <th>Archived at</th>
              <th>Archive reason</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {certifiers.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={5}>
                  No certifiers found.
                </td>
              </tr>
            ) : (
              certifiers.map((certifier) => (
                <tr
                  className={isArchived(certifier) ? "archived-row" : ""}
                  key={certifier.id}
                >
                  <td>{certifier.id}</td>
                  <td>{certifier.organization_name}</td>
                  <td>
                    {isArchived(certifier) ? (
                      <span className="badge badge-archived">
                        {formatDate(certifier.archived_at)}
                      </span>
                    ) : (
                      <span className="badge badge-active">Active</span>
                    )}
                  </td>
                  <td>{certifier.archive_reason ?? "—"}</td>
                  <td>
                    {isArchived(certifier) ? (
                      <button
                        className="button"
                        disabled={isBusy}
                        type="button"
                        onClick={() =>
                          void handleRestoreCertifier(certifier.id)
                        }
                      >
                        Restore
                      </button>
                    ) : (
                      <div className="row-actions">
                        <input
                          className="input archive-input"
                          placeholder="Optional reason"
                          value={archiveReasons[certifier.id] ?? ""}
                          onChange={(event) =>
                            updateArchiveReason(
                              certifier.id,
                              event.target.value,
                            )
                          }
                        />

                        <button
                          className="button"
                          disabled={isBusy}
                          type="button"
                          onClick={() =>
                            void handleArchiveCertifier(certifier.id)
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