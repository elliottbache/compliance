import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  ADMIN_RESOURCE_PATHS,
  archiveAdminRecord,
  createAdminRecord,
  listAdminRecords,
  restoreAdminRecord,
  uploadAttachmentFile,
} from "../../api/complianceApi";
import type { AttachmentRecord } from "../../types";
import { getErrorMessage } from "../../utils/apiErrors";

type AttachmentCreatePayload = {
  certification_id: number;
  file_name: string | null;
  description: string | null;
  finding_ids?: number[];
};

type AttachmentFormState = {
  certification_id: string;
  file_name: string;
  description: string;
  finding_ids: string;
};

const EMPTY_FORM: AttachmentFormState = {
  certification_id: "",
  file_name: "",
  description: "",
  finding_ids: "",
};

const ATTACHMENTS_PATH = ADMIN_RESOURCE_PATHS.attachments;

function isArchived(attachment: AttachmentRecord): boolean {
  return attachment.archived_at !== null;
}

function formatDate(value: string | null | undefined): string {
  return value ?? "—";
}

function getAttachmentFileLabel(attachment: AttachmentRecord): string {
  return attachment.file_name ?? "—";
}

function parseIdList(value: string): number[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map(Number)
    .filter((item) => Number.isInteger(item) && item > 0);
}

function buildCreatePayload(
  form: AttachmentFormState,
): AttachmentCreatePayload {
  const findingIds = parseIdList(form.finding_ids);

  return {
    certification_id: Number(form.certification_id),
    file_name: form.file_name.trim() || null,
    description: form.description.trim() || null,
    ...(findingIds.length > 0 ? { finding_ids: findingIds } : {}),
  };
}

export function AttachmentsSection() {
  const [attachments, setAttachments] = useState<AttachmentRecord[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [form, setForm] = useState<AttachmentFormState>(EMPTY_FORM);
  const [uploadAttachmentId, setUploadAttachmentId] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [archiveReasons, setArchiveReasons] = useState<Record<number, string>>(
    {},
  );
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAttachments = useCallback(async () => {
    try {
      setLoading("Loading attachments...");
      setError(null);
      const loadedAttachments = await listAdminRecords<AttachmentRecord>(
        ATTACHMENTS_PATH,
        { includeArchived },
      );
      setAttachments(loadedAttachments);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }, [includeArchived]);

  useEffect(() => {
    void loadAttachments();
  }, [loadAttachments]);

  function updateFormField(
    field: keyof AttachmentFormState,
    value: string,
  ): void {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: value,
    }));
  }

  function updateArchiveReason(attachmentId: number, value: string): void {
    setArchiveReasons((currentReasons) => ({
      ...currentReasons,
      [attachmentId]: value,
    }));
  }

  async function handleCreateAttachment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      setLoading("Creating attachment...");
      setError(null);
      await createAdminRecord<AttachmentCreatePayload, AttachmentRecord>(
        ATTACHMENTS_PATH,
        buildCreatePayload(form),
      );
      setForm(EMPTY_FORM);
      setShowCreateForm(false);
      await loadAttachments();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleUploadAttachment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!uploadAttachmentId || !uploadFile) {
      return;
    }

    try {
      setLoading(`Uploading attachment ${uploadAttachmentId}...`);
      setError(null);
      await uploadAttachmentFile(Number(uploadAttachmentId), uploadFile);
      setUploadAttachmentId("");
      setUploadFile(null);
      setShowUploadForm(false);
      await loadAttachments();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleArchiveAttachment(attachmentId: number) {
    try {
      setLoading(`Archiving attachment ${attachmentId}...`);
      setError(null);
      await archiveAdminRecord<AttachmentRecord>(
        ATTACHMENTS_PATH,
        attachmentId,
        archiveReasons[attachmentId],
      );
      updateArchiveReason(attachmentId, "");
      await loadAttachments();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  async function handleRestoreAttachment(attachmentId: number) {
    try {
      setLoading(`Restoring attachment ${attachmentId}...`);
      setError(null);
      await restoreAdminRecord<AttachmentRecord>(
        ATTACHMENTS_PATH,
        attachmentId,
      );
      await loadAttachments();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  const isBusy = loading !== null;
  const pendingUploadAttachments = attachments.filter(
    (attachment) => attachment.uploaded_at === null,
  );

  return (
    <section className="admin-record-section">
      <div className="admin-record-header">
        <div>
          <h3>Attachments</h3>
          <p>List, create, archive, and restore evidence metadata.</p>
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
            onClick={() => void loadAttachments()}
          >
            Refresh
          </button>

          <button
            className="button button-primary"
            disabled={isBusy}
            type="button"
            onClick={() => {
              setShowUploadForm(false);
              setShowCreateForm((current) => !current);
            }}
          >
            {showCreateForm ? "Cancel" : "Add Attachment"}
          </button>

          <button
            className="button button-primary"
            disabled={isBusy || pendingUploadAttachments.length === 0}
            type="button"
            onClick={() => {
              setShowCreateForm(false);
              setShowUploadForm((current) => !current);
            }}
          >
            {showUploadForm ? "Cancel" : "Upload File"}
          </button>
        </div>
      </div>

      {loading ? <p className="loading-text">{loading}</p> : null}
      {error ? <div className="error-box">{error}</div> : null}

      {showCreateForm ? (
        <form className="admin-form" onSubmit={handleCreateAttachment}>
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

            <label className="form-grid-wide">
              File name
              <input
                required
                className="input"
                placeholder="inspection_report"
                value={form.file_name}
                onChange={(event) =>
                  updateFormField("file_name", event.target.value)
                }
              />
            </label>

            <label className="form-grid-wide">
              Description
              <textarea
                className="textarea admin-textarea"
                value={form.description}
                onChange={(event) =>
                  updateFormField("description", event.target.value)
                }
              />
            </label>

            <label className="form-grid-wide">
              Finding IDs, optional comma-separated
              <input
                className="input"
                placeholder="Example: 3, 8, 12"
                value={form.finding_ids}
                onChange={(event) =>
                  updateFormField("finding_ids", event.target.value)
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

      {showUploadForm ? (
        <form className="admin-form" onSubmit={handleUploadAttachment}>
          <div className="form-grid">
            <label>
              Attachment
              <select
                required
                className="select"
                value={uploadAttachmentId}
                onChange={(event) =>
                  setUploadAttachmentId(event.target.value)
                }
              >
                <option value="">Select attachment</option>
                {pendingUploadAttachments.map((attachment) => (
                  <option key={attachment.id} value={attachment.id}>
                    {attachment.id} - {getAttachmentFileLabel(attachment)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              File
              <input
                required
                className="input"
                type="file"
                onChange={(event) =>
                  setUploadFile(event.target.files?.[0] ?? null)
                }
              />
            </label>
          </div>

          <div className="button-row">
            <button
              className="button button-primary"
              disabled={isBusy || pendingUploadAttachments.length === 0}
              type="submit"
            >
              Upload
            </button>

            <button
              className="button"
              disabled={isBusy}
              type="button"
              onClick={() => {
                setUploadAttachmentId("");
                setUploadFile(null);
                setShowUploadForm(false);
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
              <th>File type</th>
              <th>File</th>
              <th>Description</th>
              <th>Uploaded at</th>
              <th>Archived at</th>
              <th>Archive reason</th>
              <th>Actions</th>
            </tr>
          </thead>

          <tbody>
            {attachments.length === 0 ? (
              <tr>
                <td className="empty-table-cell" colSpan={9}>
                  No attachments found.
                </td>
              </tr>
            ) : (
              attachments.map((attachment) => (
                <tr
                  className={isArchived(attachment) ? "archived-row" : ""}
                  key={attachment.id}
                >
                  <td>{attachment.id}</td>
                  <td>{attachment.certification_id}</td>
                  <td>
                    {attachment.file_path?.includes(".")
                      ? attachment.file_path.split(".").pop()
                      : "—"}
                  </td>
                  <td>{getAttachmentFileLabel(attachment)}</td>
                  <td>{attachment.description ?? "—"}</td>
                  <td>{formatDate(attachment.uploaded_at)}</td>
                  <td>
                    {isArchived(attachment) ? (
                      <span className="badge badge-archived">
                        {formatDate(attachment.archived_at)}
                      </span>
                    ) : (
                      <span className="badge badge-active">Active</span>
                    )}
                  </td>
                  <td>{attachment.archive_reason ?? "—"}</td>
                  <td>
                    {isArchived(attachment) ? (
                      <button
                        className="button"
                        disabled={isBusy}
                        type="button"
                        onClick={() =>
                          void handleRestoreAttachment(attachment.id)
                        }
                      >
                        Restore
                      </button>
                    ) : (
                      <div className="row-actions">
                        <input
                          className="input archive-input"
                          placeholder="Optional reason"
                          value={archiveReasons[attachment.id] ?? ""}
                          onChange={(event) =>
                            updateArchiveReason(
                              attachment.id,
                              event.target.value,
                            )
                          }
                        />

                        <button
                          className="button"
                          disabled={isBusy}
                          type="button"
                          onClick={() =>
                            void handleArchiveAttachment(attachment.id)
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
