import type { SiteAttachmentsOut } from "../types";

type AttachmentsPanelProps = {
  attachments: SiteAttachmentsOut | null;
};

function formatDate(value: string | null): string {
  return value ?? "—";
}

function getFileLabel(filePath: string | null): string {
  if (!filePath) {
    return "Pending upload";
  }

  const parts = filePath.split(/[\\/]/);
  return parts[parts.length - 1] || filePath;
}

export function AttachmentsPanel({ attachments }: AttachmentsPanelProps) {
  if (!attachments) {
    return (
      <section className="result-panel">
        <div className="result-panel-header">
          <h3>Attachments</h3>
          <p>Load attachments to view evidence linked to this site.</p>
        </div>

        <div className="empty-state">No attachments loaded.</div>
      </section>
    );
  }

  return (
    <section className="result-panel">
      <div className="result-panel-header">
        <div>
          <h3>Attachments</h3>
          <p>
            Site {attachments.site_id} · {attachments.attachments.length} file
            {attachments.attachments.length === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      <div className="attachments-list">
        {attachments.attachments.length === 0 ? (
          <div className="empty-state">No attachments found.</div>
        ) : (
          attachments.attachments.map((attachment) => (
            <article
              className={
                attachment.archived_at
                  ? "attachment-card archived-row"
                  : "attachment-card"
              }
              key={attachment.id}
            >
              <div className="attachment-card-header">
                <div>
                  <h4>{attachment.file_name ?? getFileLabel(attachment.file_path)}</h4>
                  <p>{attachment.description ?? "No description"}</p>
                </div>

                <div className="badge-row">
                  <span className="badge">
                    {attachment.file_path?.includes(".")
                      ? attachment.file_path.split(".").pop()
                      : null}
                  </span>
                  {attachment.archived_at ? (
                    <span className="badge badge-archived">Archived</span>
                  ) : null}
                </div>
              </div>

              <dl className="metadata-grid">
                <div>
                  <dt>Attachment ID</dt>
                  <dd>{attachment.id}</dd>
                </div>

                <div>
                  <dt>Certification ID</dt>
                  <dd>{attachment.certification_id}</dd>
                </div>

                <div>
                  <dt>Uploaded</dt>
                  <dd>{formatDate(attachment.uploaded_at)}</dd>
                </div>

                <div>
                  <dt>Inspection date</dt>
                  <dd>{formatDate(attachment.inspection_date)}</dd>
                </div>
              </dl>

              <div className="attachment-context">
                <strong>{attachment.regulation_title}</strong>
                <span>Regulation ID: {attachment.regulation_id}</span>
              </div>

              <div className="findings-block">
                <h5>Linked findings</h5>

                {attachment.finding_links.length === 0 ? (
                  <p className="muted">No linked findings.</p>
                ) : (
                  <ul className="findings-list">
                    {attachment.finding_links.map((finding) => (
                      <li key={finding.finding_id}>
                        <div className="finding-title">
                          <span>{finding.rule_index}</span>
                          <strong>{finding.rule_title ?? "Untitled rule"}</strong>
                        </div>

                        <p>{finding.finding}</p>
                        <p className="muted">{finding.rule_description}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {attachment.archive_reason ? (
                <p className="archive-reason">
                  Archive reason: {attachment.archive_reason}
                </p>
              ) : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
