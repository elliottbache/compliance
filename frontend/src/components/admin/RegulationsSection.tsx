import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  ADMIN_RESOURCE_PATHS,
  archiveAdminRecord,
  createAdminRecord,
  listAdminRecords,
  restoreAdminRecord,
} from "../../api/complianceApi";
import type { RegulationRecord } from "../../types";
import { getErrorMessage } from "../../utils/apiErrors";

type RegulationCreatePayload = {
  title: string;
  description: string;
  published_date: string;
};

type RegulationFormState = {
  title: string;
  description: string;
  published_date: string;
};

const EMPTY_FORM: RegulationFormState = {
  title: "",
  description: "",
  published_date: "",
};

const REGULATIONS_PATH = ADMIN_RESOURCE_PATHS.regulations;

function isArchived(regulation: RegulationRecord): boolean {
  return regulation.archived_at !== null;
}

function buildCreatePayload(form: RegulationFormState): RegulationCreatePayload {
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    published_date: form.published_date,
  };
}

function formatDate(value: string | null): string {
  return value ?? "—";
}

export function RegulationsSection() {
  const [regulations, setRegulations] = useState<RegulationRecord[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState<RegulationFormState>(EMPTY_FORM);
  const [archiveReasons, setArchiveReasons] = useState<Record<number, string>>(
    {},
  );
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadRegulations = useCallback(async () => {
    try {
      setLoading("Loading regulations...");
      setError(null);
      const loadedRegulations = await listAdminRecords<RegulationRecord>(
        REGULATIONS_PATH,
        { includeArchived },
      );
      setRegulations(loadedRegulations);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }, [includeArchived]);

  useEffect(() => {
    void loadRegulations();
  }, [loadRegulations]);

  function updateFormField(
    field: keyof RegulationFormState,
    value: string,
  ): void {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: value,
    }));
  }

  function updateArchiveReason(regulationId: number, value: string): void {
    setArchiveReasons((currentReasons) => ({
      ...currentReasons,
      [regulationId]: value,
    }));
  }

  async function handleCreateRegulation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading("Creating regulation...");
      setError(null);
      await createAdminRecord<RegulationCreatePayload, RegulationRecord>(
        REGULATIONS_PATH,
        buildCreatePayload(form),
      );
      setForm(EMPTY_FORM);
      setShowCreateForm(false);
      await loadRegulations();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleArchiveRegulation(regulationId: number) {
    try {
      setLoading(`Archiving regulation ${regulationId}...`);
      setError(null);
      await archiveAdminRecord<RegulationRecord>(
        REGULATIONS_PATH,
        regulationId,
        archiveReasons[regulationId],
      );
      updateArchiveReason(regulationId, "");
      await loadRegulations();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleRestoreRegulation(regulationId: number) {
    try {
      setLoading(`Restoring regulation ${regulationId}...`);
      setError(null);
      await restoreAdminRecord<RegulationRecord>(
        REGULATIONS_PATH,
        regulationId,
      );
      await loadRegulations();
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
          <h3>Regulations</h3>
          <p>List, create, archive, and restore compliance frameworks.</p>
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
            onClick={() => void loadRegulations()}
          >
            Refresh
          </button>

          <button
            className="button button-primary"
            disabled={isBusy}
            type="button"
            onClick={() => setShowCreateForm((current) => !current)}
          >
            {showCreateForm ? "Cancel" : "Add Regulation"}
          </button>
        </div>
      </div>

      {loading ? <p className="loading-text">{loading}</p> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {showCreateForm ? (
        <form className="admin-form" onSubmit={handleCreateRegulation}>
          <div className="form-grid">
            <label>
              Title
              <input
                required
                className="input"
                value={form.title}
                onChange={(event) => updateFormField("title", event.target.value)}
              />
            </label>

            <label>
            Published date
            <input
                required
                className="input"
                type="date"
                value={form.published_date}
                onChange={(event) =>
                updateFormField("published_date", event.target.value)
                }
            />
            </label>

            <label className="form-grid-wide">
              Description
              <textarea
                required
                className="textarea admin-textarea"
                value={form.description}
                onChange={(event) =>
                  updateFormField("description", event.target.value)
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
              <th>Title</th>
              <th>Published date</th>
              <th>Description</th>
              <th>Archived at</th>
              <th>Archive reason</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {regulations.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={7}>
                  No regulations found.
                </td>
              </tr>
            ) : (
              regulations.map((regulation) => (
                <tr
                  className={isArchived(regulation) ? "archived-row" : ""}
                  key={regulation.id}
                >
                  <td>{regulation.id}</td>
                  <td>{regulation.title}</td>
                  <td>{regulation.published_date}</td>
                  <td>{regulation.description}</td>
                  <td>
                    {isArchived(regulation) ? (
                      <span className="badge badge-archived">
                        {formatDate(regulation.archived_at)}
                      </span>
                    ) : (
                      <span className="badge badge-active">Active</span>
                    )}
                  </td>
                  <td>{regulation.archive_reason ?? "—"}</td>
                  <td>
                    {isArchived(regulation) ? (
                      <button
                        className="button"
                        disabled={isBusy}
                        type="button"
                        onClick={() =>
                          void handleRestoreRegulation(regulation.id)
                        }
                      >
                        Restore
                      </button>
                    ) : (
                      <div className="row-actions">
                        <input
                          className="input archive-input"
                          placeholder="Optional reason"
                          value={archiveReasons[regulation.id] ?? ""}
                          onChange={(event) =>
                            updateArchiveReason(
                              regulation.id,
                              event.target.value,
                            )
                          }
                        />

                        <button
                          className="button"
                          disabled={isBusy}
                          type="button"
                          onClick={() =>
                            void handleArchiveRegulation(regulation.id)
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