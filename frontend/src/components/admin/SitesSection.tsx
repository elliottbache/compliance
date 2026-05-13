import { useCallback, useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import {
  ADMIN_RESOURCE_PATHS,
  archiveAdminRecord,
  createAdminRecord,
  listAdminRecords,
  restoreAdminRecord,
} from "../../api/complianceApi";
import type { SiteRecord } from "../../types";
import { getErrorMessage } from "../../utils/apiErrors";

type SiteCreatePayload = {
  nif: string;
  city: string;
  postal_code: number;
  street: string;
  street_number: number | null;
  suite: string | null;
  address_info: string | null;
};

type SiteFormState = {
  client_nif: string;
  city: string;
  postal_code: string;
  street: string;
  street_number: string;
  suite: string;
  address_info: string;
};

const EMPTY_FORM: SiteFormState = {
  client_nif: "",
  city: "",
  postal_code: "",
  street: "",
  street_number: "",
  suite: "",
  address_info: "",
};

const SITES_PATH = ADMIN_RESOURCE_PATHS.sites;

function isArchived(site: SiteRecord): boolean {
  return site.archived_at !== null;
}

function formatAddress(site: SiteRecord): string {
  return [site.street, site.street_number, site.suite]
    .filter(Boolean)
    .join(", ");
}

function buildCreatePayload(form: SiteFormState): SiteCreatePayload {
  return {
    nif: form.client_nif.trim(),
    city: form.city.trim(),
    postal_code: Number(form.postal_code),
    street: form.street.trim(),
    street_number: form.street_number.trim()
      ? Number(form.street_number)
      : null,
    suite: form.suite.trim() || null,
    address_info: form.address_info.trim() || null,
  };
}

export function SitesSection() {
  const [sites, setSites] = useState<SiteRecord[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState<SiteFormState>(EMPTY_FORM);
  const [archiveReasons, setArchiveReasons] = useState<Record<number, string>>(
    {},
  );
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSites = useCallback(async () => {
    try {
      setLoading("Loading sites...");
      setError(null);
      const loadedSites = await listAdminRecords<SiteRecord>(SITES_PATH, {
        includeArchived,
      });
      setSites(loadedSites);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }, [includeArchived]);

  useEffect(() => {
    void loadSites();
  }, [loadSites]);

  function updateFormField(
    field: keyof SiteFormState,
    event: ChangeEvent<HTMLInputElement>,
  ): void {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: event.target.value,
    }));
  }

  function updateArchiveReason(siteId: number, value: string): void {
    setArchiveReasons((currentReasons) => ({
      ...currentReasons,
      [siteId]: value,
    }));
  }

  async function handleCreateSite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading("Creating site...");
      setError(null);
      await createAdminRecord<SiteCreatePayload, SiteRecord>(
        SITES_PATH,
        buildCreatePayload(form),
      );
      setForm(EMPTY_FORM);
      setShowCreateForm(false);
      await loadSites();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleArchiveSite(siteId: number) {
    try {
      setLoading(`Archiving site ${siteId}...`);
      setError(null);
      await archiveAdminRecord<SiteRecord>(
        SITES_PATH,
        siteId,
        archiveReasons[siteId],
      );
      updateArchiveReason(siteId, "");
      await loadSites();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleRestoreSite(siteId: number) {
    try {
      setLoading(`Restoring site ${siteId}...`);
      setError(null);
      await restoreAdminRecord<SiteRecord>(SITES_PATH, siteId);
      await loadSites();
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
          <h3>Sites</h3>
          <p>List, create, archive, and restore inspected locations.</p>
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
            onClick={() => void loadSites()}
          >
            Refresh
          </button>

          <button
            className="button button-primary"
            disabled={isBusy}
            type="button"
            onClick={() => setShowCreateForm((current) => !current)}
          >
            {showCreateForm ? "Cancel" : "Add Site"}
          </button>
        </div>
      </div>

      {loading ? <p className="loading-text">{loading}</p> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {showCreateForm ? (
        <form className="admin-form" onSubmit={handleCreateSite}>
          <div className="form-grid">
            <label>
              Client NIF / Site NIF
              <input
                required
                className="input"
                value={form.client_nif}
                onChange={(event) => updateFormField("client_nif", event)}
              />
            </label>

            <label>
              City
              <input
                required
                className="input"
                value={form.city}
                onChange={(event) => updateFormField("city", event)}
              />
            </label>

            <label>
              Postal code
              <input
                required
                className="input"
                value={form.postal_code}
                onChange={(event) => updateFormField("postal_code", event)}
              />
            </label>

            <label>
              Street
              <input
                required
                className="input"
                value={form.street}
                onChange={(event) => updateFormField("street", event)}
              />
            </label>

            <label>
              Street number
              <input
                required
                className="input"
                value={form.street_number}
                onChange={(event) => updateFormField("street_number", event)}
              />
            </label>

            <label>
              Suite
              <input
                className="input"
                value={form.suite}
                onChange={(event) => updateFormField("suite", event)}
              />
            </label>

            <label className="form-grid-wide">
              Address info
              <input
                className="input"
                value={form.address_info}
                onChange={(event) => updateFormField("address_info", event)}
              />
            </label>
          </div>

          <div className="button-row">
            <button className="button button-primary" disabled={isBusy} type="submit">
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
              <th>Client NIF</th>
              <th>City</th>
              <th>Address</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {sites.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={6}>
                  No sites found.
                </td>
              </tr>
            ) : (
              sites.map((site) => (
                <tr className={isArchived(site) ? "archived-row" : ""} key={site.id}>
                  <td>{site.id}</td>
                  <td>{site.client_nif}</td>
                  <td>{site.city}</td>
                  <td>
                    <div>{formatAddress(site)}</div>
                    {site.address_info ? (
                      <span className="muted">{site.address_info}</span>
                    ) : null}
                  </td>
                  <td>
                    {isArchived(site) ? (
                      <span className="badge badge-archived">Archived</span>
                    ) : (
                      <span className="badge badge-active">Active</span>
                    )}
                  </td>
                  <td>
                    {isArchived(site) ? (
                      <button
                        className="button"
                        disabled={isBusy}
                        type="button"
                        onClick={() => void handleRestoreSite(site.id)}
                      >
                        Restore
                      </button>
                    ) : (
                      <div className="row-actions">
                        <input
                          className="input archive-input"
                          placeholder="Optional reason"
                          value={archiveReasons[site.id] ?? ""}
                          onChange={(event) =>
                            updateArchiveReason(site.id, event.target.value)
                          }
                        />

                        <button
                          className="button"
                          disabled={isBusy}
                          type="button"
                          onClick={() => void handleArchiveSite(site.id)}
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