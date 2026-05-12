import type { CertificationHistory, SiteHistory } from "../types";

type SiteHistoryPanelProps = {
  history: SiteHistory | null;
};

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  return value;
}

function formatResult(result: CertificationHistory["result"]): string {
  return result ?? "Pending";
}

export function SiteHistoryPanel({ history }: SiteHistoryPanelProps) {
  if (!history) {
    return (
      <section className="result-panel">
        <div className="result-panel-header">
          <h3>Site history</h3>
          <p>Load history to view inspections and findings.</p>
        </div>

        <div className="empty-state">No site history loaded.</div>
      </section>
    );
  }

  return (
    <section className="result-panel">
      <div className="result-panel-header">
        <div>
          <h3>Site history</h3>
          <p>
            Site {history.site_id} · {history.inspection_count} inspection
            {history.inspection_count === 1 ? "" : "s"}
          </p>
        </div>

        <span className="badge">
          Latest: {formatDate(history.latest_inspection_date)}
        </span>
      </div>

      <div className="history-list">
        {history.certifications.length === 0 ? (
          <div className="empty-state">No certifications found.</div>
        ) : (
          history.certifications.map((certification) => (
            <article className="history-card" key={certification.cert_id}>
              <div className="history-card-header">
                <div>
                  <h4>{certification.reg_title}</h4>
                  <p>{certification.reg_description}</p>
                </div>

                <span
                  className={
                    certification.result === "Fail"
                      ? "badge badge-fail"
                      : "badge badge-active"
                  }
                >
                  {formatResult(certification.result)}
                </span>
              </div>

              <dl className="metadata-grid">
                <div>
                  <dt>Certification ID</dt>
                  <dd>{certification.cert_id}</dd>
                </div>

                <div>
                  <dt>Certifier</dt>
                  <dd>{certification.certifier_org_name}</dd>
                </div>

                <div>
                  <dt>Inspection date</dt>
                  <dd>{formatDate(certification.inspection_date)}</dd>
                </div>

                <div>
                  <dt>Resolution date</dt>
                  <dd>{formatDate(certification.resolution_date)}</dd>
                </div>
              </dl>

              <div className="findings-block">
                <h5>Findings</h5>

                {certification.findings.length === 0 ? (
                  <p className="muted">No findings recorded.</p>
                ) : (
                  <ul className="findings-list">
                    {certification.findings.map((finding) => (
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
            </article>
          ))
        )}
      </div>
    </section>
  );
}