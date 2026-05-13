import type { SiteAnalysis } from "../types";

type AnalysisPanelProps = {
  analysis: SiteAnalysis | null;
};

export function AnalysisPanel({ analysis }: AnalysisPanelProps) {
  if (!analysis) {
    return (
      <section className="result-panel">
        <div className="result-panel-header">
          <div>
            <h3>AI Analysis Preview</h3>
            <p>Human review required. Run analysis to generate a draft preview.</p>
          </div>

          <span className="badge badge-warning">Not run</span>
        </div>

        <div className="empty-state">No AI analysis loaded.</div>
      </section>
    );
  }

  return (
    <section className="result-panel">
      <div className="result-panel-header">
        <div>
          <h3>AI Analysis Preview</h3>
          <p>
            Draft analysis only. Human review required before any compliance
            decision.
          </p>
        </div>

        <span className="badge badge-warning">Human review required</span>
      </div>

      <div className="safety-note">
        AI output may summarize evidence and recurring issues, but it must not
        certify, reject, approve, or decide pass/fail.
      </div>

      <pre className="code-box">{JSON.stringify(analysis, null, 2)}</pre>
    </section>
  );
}