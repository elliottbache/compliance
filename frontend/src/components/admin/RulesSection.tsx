import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  ADMIN_RESOURCE_PATHS,
  archiveAdminRecord,
  createAdminRecord,
  listAdminRecords,
  restoreAdminRecord,
} from "../../api/complianceApi";
import type { RuleRecord } from "../../types";
import { getErrorMessage } from "../../utils/apiErrors";

type RuleCreatePayload = {
  regulation_id: number;
  rule_index: string;
  title: string | null;
  description: string;
};

type RuleFormState = {
  regulation_id: string;
  rule_index: string;
  title: string;
  description: string;
};

const EMPTY_FORM: RuleFormState = {
  regulation_id: "",
  rule_index: "",
  title: "",
  description: "",
};

const RULES_PATH = ADMIN_RESOURCE_PATHS.rules;

function isArchived(rule: RuleRecord): boolean {
  return rule.archived_at !== null;
}

function buildCreatePayload(form: RuleFormState): RuleCreatePayload {
  return {
    regulation_id: Number(form.regulation_id),
    rule_index: form.rule_index.trim(),
    title: form.title.trim() || null,
    description: form.description.trim(),
  };
}

function formatDate(value: string | null): string {
  return value ?? "—";
}

export function RulesSection() {
  const [rules, setRules] = useState<RuleRecord[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form, setForm] = useState<RuleFormState>(EMPTY_FORM);
  const [archiveReasons, setArchiveReasons] = useState<Record<number, string>>(
    {},
  );
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadRules = useCallback(async () => {
    try {
      setLoading("Loading rules...");
      setError(null);
      const loadedRules = await listAdminRecords<RuleRecord>(RULES_PATH, {
        includeArchived,
      });
      setRules(loadedRules);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }, [includeArchived]);

  useEffect(() => {
    void loadRules();
  }, [loadRules]);

  function updateFormField(field: keyof RuleFormState, value: string): void {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: value,
    }));
  }

  function updateArchiveReason(ruleId: number, value: string): void {
    setArchiveReasons((currentReasons) => ({
      ...currentReasons,
      [ruleId]: value,
    }));
  }

  async function handleCreateRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading("Creating rule...");
      setError(null);
      await createAdminRecord<RuleCreatePayload, RuleRecord>(
        RULES_PATH,
        buildCreatePayload(form),
      );
      setForm(EMPTY_FORM);
      setShowCreateForm(false);
      await loadRules();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleArchiveRule(ruleId: number) {
    try {
      setLoading(`Archiving rule ${ruleId}...`);
      setError(null);
      await archiveAdminRecord<RuleRecord>(
        RULES_PATH,
        ruleId,
        archiveReasons[ruleId],
      );
      updateArchiveReason(ruleId, "");
      await loadRules();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleRestoreRule(ruleId: number) {
    try {
      setLoading(`Restoring rule ${ruleId}...`);
      setError(null);
      await restoreAdminRecord<RuleRecord>(RULES_PATH, ruleId);
      await loadRules();
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
          <h3>Rules</h3>
          <p>List, create, archive, and restore regulation rules.</p>
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
            onClick={() => void loadRules()}
          >
            Refresh
          </button>

          <button
            className="button button-primary"
            disabled={isBusy}
            type="button"
            onClick={() => setShowCreateForm((current) => !current)}
          >
            {showCreateForm ? "Cancel" : "Add Rule"}
          </button>
        </div>
      </div>

      {loading ? <p className="loading-text">{loading}</p> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {showCreateForm ? (
        <form className="admin-form" onSubmit={handleCreateRule}>
          <div className="form-grid">
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
              Rule index
              <input
                required
                className="input"
                value={form.rule_index}
                onChange={(event) =>
                  updateFormField("rule_index", event.target.value)
                }
              />
            </label>

            <label className="form-grid-wide">
              Title
              <input
                className="input"
                value={form.title}
                onChange={(event) => updateFormField("title", event.target.value)}
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
              <th>Regulation ID</th>
              <th>Index</th>
              <th>Title</th>
              <th>Description</th>
              <th>Archived at</th>
              <th>Archive reason</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {rules.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={8}>
                  No rules found.
                </td>
              </tr>
            ) : (
              rules.map((rule) => (
                <tr
                  className={isArchived(rule) ? "archived-row" : ""}
                  key={rule.id}
                >
                  <td>{rule.id}</td>
                  <td>{rule.regulation_id}</td>
                  <td>{rule.rule_index}</td>
                  <td>{rule.title ?? "—"}</td>
                  <td>{rule.description}</td>
                  <td>
                    {isArchived(rule) ? (
                      <span className="badge badge-archived">
                        {formatDate(rule.archived_at)}
                      </span>
                    ) : (
                      <span className="badge badge-active">Active</span>
                    )}
                  </td>
                  <td>{rule.archive_reason ?? "—"}</td>
                  <td>
                    {isArchived(rule) ? (
                      <button
                        className="button"
                        disabled={isBusy}
                        type="button"
                        onClick={() => void handleRestoreRule(rule.id)}
                      >
                        Restore
                      </button>
                    ) : (
                      <div className="row-actions">
                        <input
                          className="input archive-input"
                          placeholder="Optional reason"
                          value={archiveReasons[rule.id] ?? ""}
                          onChange={(event) =>
                            updateArchiveReason(rule.id, event.target.value)
                          }
                        />

                        <button
                          className="button"
                          disabled={isBusy}
                          type="button"
                          onClick={() => void handleArchiveRule(rule.id)}
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