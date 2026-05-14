import { useCallback, useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import {
  ADMIN_RESOURCE_PATHS,
  archiveAdminRecord,
  createAdminRecord,
  listAdminRecords,
  restoreAdminRecord,
} from "../../api/complianceApi";
import type { ClientRecord } from "../../types";
import {
  formatArchivedAt,
  formatArchiveReason,
} from "../../utils/adminFormatters";
import { getErrorMessage } from "../../utils/apiErrors";

type ClientCreatePayload = {
  nif: string;
  company_name: string;
  contact_name: string | null;
  email: string | null;
  telephone: string | null;
};

type ClientFormState = {
  nif: string;
  company_name: string;
  contact_name: string;
  email: string;
  telephone: string;
};

const EMPTY_FORM: ClientFormState = {
  nif: "",
  company_name: "",
  contact_name: "",
  email: "",
  telephone: "",
};

const CLIENTS_PATH = ADMIN_RESOURCE_PATHS.clients;

function isArchived(client: ClientRecord): boolean {
  return client.archived_at !== null;
}

function buildCreatePayload(form: ClientFormState): ClientCreatePayload {
  return {
    nif: form.nif.trim(),
    company_name: form.company_name.trim(),
    contact_name: form.contact_name.trim() || null,
    email: form.email.trim() || null,
    telephone: form.telephone.trim() || null,
  };
}

export function ClientsSection() {
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState<ClientFormState>(EMPTY_FORM);
  const [archiveReasons, setArchiveReasons] = useState<Record<string, string>>(
    {},
  );
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadClients = useCallback(async () => {
    try {
      setLoading("Loading clients...");
      setError(null);
      const loadedClients = await listAdminRecords<ClientRecord>(CLIENTS_PATH, {
        includeArchived,
      });
      setClients(loadedClients);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }, [includeArchived]);

  useEffect(() => {
    void loadClients();
  }, [loadClients]);

  function updateFormField(
    field: keyof ClientFormState,
    event: ChangeEvent<HTMLInputElement>,
  ): void {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: event.target.value,
    }));
  }

  function updateArchiveReason(nif: string, value: string): void {
    setArchiveReasons((currentReasons) => ({
      ...currentReasons,
      [nif]: value,
    }));
  }

  async function handleCreateClient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading("Creating client...");
      setError(null);
      await createAdminRecord<ClientCreatePayload, ClientRecord>(
        CLIENTS_PATH,
        buildCreatePayload(form),
      );
      setForm(EMPTY_FORM);
      setShowCreateForm(false);
      await loadClients();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleArchiveClient(nif: string) {
    try {
      setLoading(`Archiving client ${nif}...`);
      setError(null);
      await archiveAdminRecord<ClientRecord>(
        CLIENTS_PATH,
        nif,
        archiveReasons[nif],
      );
      updateArchiveReason(nif, "");
      await loadClients();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleRestoreClient(nif: string) {
    try {
      setLoading(`Restoring client ${nif}...`);
      setError(null);
      await restoreAdminRecord<ClientRecord>(CLIENTS_PATH, nif);
      await loadClients();
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
          <h3>Clients</h3>
          <p>List, create, archive, and restore client companies.</p>
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
            onClick={() => void loadClients()}
          >
            Refresh
          </button>

          <button
            className="button button-primary"
            disabled={isBusy}
            type="button"
            onClick={() => setShowCreateForm((current) => !current)}
          >
            {showCreateForm ? "Cancel" : "Add Client"}
          </button>
        </div>
      </div>

      {loading ? <p className="loading-text">{loading}</p> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {showCreateForm ? (
        <form className="admin-form" onSubmit={handleCreateClient}>
          <div className="form-grid">
            <label>
              NIF
              <input
                required
                className="input"
                maxLength={9}
                minLength={9}
                value={form.nif}
                onChange={(event) => updateFormField("nif", event)}
              />
            </label>

            <label>
              Company name
              <input
                required
                className="input"
                value={form.company_name}
                onChange={(event) => updateFormField("company_name", event)}
              />
            </label>

            <label>
              Contact name
              <input
                className="input"
                value={form.contact_name}
                onChange={(event) => updateFormField("contact_name", event)}
              />
            </label>

            <label>
              Email
              <input
                className="input"
                type="email"
                value={form.email}
                onChange={(event) => updateFormField("email", event)}
              />
            </label>

            <label>
              Telephone
              <input
                className="input"
                value={form.telephone}
                onChange={(event) => updateFormField("telephone", event)}
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
              <th>NIF</th>
              <th>Company</th>
              <th>Contact</th>
              <th>Email</th>
              <th>Telephone</th>
              <th>Archived at</th>
              <th>Archive reason</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {clients.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={8}>
                  No clients found.
                </td>
              </tr>
            ) : (
              clients.map((client) => (
                <tr
                  className={isArchived(client) ? "archived-row" : ""}
                  key={client.nif}
                >
                  <td>{client.nif}</td>
                  <td>{client.company_name}</td>
                  <td>{client.contact_name ?? "—"}</td>
                  <td>{client.email ?? "—"}</td>
                  <td>{client.telephone ?? "—"}</td>
                  <td>
                    {isArchived(client) ? (
                      <span className="badge badge-archived">
                        {formatArchivedAt(client.archived_at)}
                      </span>
                    ) : (
                      <span className="badge badge-active">Active</span>
                    )}
                  </td>
                  <td>{formatArchiveReason(client.archive_reason)}</td>
                  <td>
                    {isArchived(client) ? (
                      <button
                        className="button"
                        disabled={isBusy}
                        type="button"
                        onClick={() => void handleRestoreClient(client.nif)}
                      >
                        Restore
                      </button>
                    ) : (
                      <div className="row-actions">
                        <input
                          className="input archive-input"
                          placeholder="Optional reason"
                          value={archiveReasons[client.nif] ?? ""}
                          onChange={(event) =>
                            updateArchiveReason(client.nif, event.target.value)
                          }
                        />

                        <button
                          className="button"
                          disabled={isBusy}
                          type="button"
                          onClick={() => void handleArchiveClient(client.nif)}
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
