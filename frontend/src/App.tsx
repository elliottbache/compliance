import { useState } from "react";
import {
  createSiteAnalysis,
  createSiteAnalysisMarkdown,
  getSiteAttachments,
  getSiteHistory,
} from "./api/complianceApi";
import { SiteSearchPanel } from "./components/SiteSearchPanel";
import { SiteHistoryPanel } from "./components/SiteHistoryPanel";
import type {
  ApiErrorMessage,
  LoadingState,
  SiteAnalysis,
  SiteAttachmentsOut,
  SiteHistory,
} from "./types";

const workflowItems = [
  "Enter site ID",
  "Load inspection history",
  "Load attachments",
  "Run AI analysis",
  "Generate Markdown report",
];

const adminSections = [
  "Sites",
  "Clients",
  "Certifiers",
  "Regulations",
  "Rules",
  "Certifications",
  "Findings",
  "Attachments",
];

function parseSiteId(siteId: string): number {
  const parsed = Number(siteId);

  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("Enter a valid positive numeric site ID.");
  }

  return parsed;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected error";
}

function App() {
  const [siteId, setSiteId] = useState("1");
  const [history, setHistory] = useState<SiteHistory | null>(null);
  const [attachments, setAttachments] = useState<SiteAttachmentsOut | null>(
    null,
  );
  const [analysis, setAnalysis] = useState<SiteAnalysis | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState<ApiErrorMessage>(null);
  const [loading, setLoading] = useState<LoadingState>(null);

  async function runAction(
    actionName: NonNullable<LoadingState>,
    action: (parsedSiteId: number) => Promise<void>,
  ): Promise<void> {
    try {
      setError(null);
      setLoading(actionName);
      await action(parseSiteId(siteId));
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setLoading(null);
    }
  }

  function handleLoadHistory(): void {
    void runAction("history", async (parsedSiteId) => {
      const loadedHistory = await getSiteHistory(parsedSiteId);
      setHistory(loadedHistory);
    });
  }

  function handleLoadAttachments(): void {
    void runAction("attachments", async (parsedSiteId) => {
      const loadedAttachments = await getSiteAttachments(parsedSiteId);
      setAttachments(loadedAttachments);
    });
  }

  function handleRunAnalysis(): void {
    void runAction("analysis", async (parsedSiteId) => {
      const loadedAnalysis = await createSiteAnalysis(parsedSiteId);
      setAnalysis(loadedAnalysis);
    });
  }

  function handleGenerateMarkdown(): void {
    void runAction("markdown", async (parsedSiteId) => {
      const loadedMarkdown = await createSiteAnalysisMarkdown(parsedSiteId);
      setMarkdown(loadedMarkdown);
    });
  }

  function handleClear(): void {
    setHistory(null);
    setAttachments(null);
    setAnalysis(null);
    setMarkdown("");
    setError(null);
    setLoading(null);
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Compliance MVP</p>
          <h1>Inspection Dashboard</h1>
          <p className="app-subtitle">
            Thin frontend for site history, evidence review, and human-reviewed
            AI analysis.
          </p>
        </div>

        <div className="status-pill">Local demo</div>
      </header>

      <section className="hero-panel">
        <div>
          <p className="eyebrow">Primary workflow</p>
          <h2>Site analysis workspace</h2>
          <p>
            Load factual inspection data first. Run AI only when explicitly
            requested.
          </p>
        </div>

        <div className="workflow-strip">
          {workflowItems.map((item, index) => (
            <div className="workflow-step" key={item}>
              <span>{index + 1}</span>
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className="dashboard-grid">
        <section className="panel panel-large">
          <div className="panel-header">
            <div>
              <h2>Site workflow</h2>
              <p>History, attachments, AI preview, and Markdown report.</p>
            </div>
          </div>

          <div className="panel-body">
            <SiteSearchPanel
              loading={loading}
              siteId={siteId}
              onClear={handleClear}
              onGenerateMarkdown={handleGenerateMarkdown}
              onLoadAttachments={handleLoadAttachments}
              onLoadHistory={handleLoadHistory}
              onRunAnalysis={handleRunAnalysis}
              onSiteIdChange={setSiteId}
            />

            {error ? <div className="error-box">{error}</div> : null}

            <div className="result-summary">
              <div className="summary-card">
                <span>History</span>
                <strong>
                  {history
                    ? `${history.inspection_count} inspections`
                    : "Not loaded"}
                </strong>
              </div>
              <SiteHistoryPanel history={history} />

              <div className="summary-card">
                <span>Attachments</span>
                <strong>
                  {attachments
                    ? `${attachments.attachments.length} files`
                    : "Not loaded"}
                </strong>
              </div>

              <div className="summary-card">
                <span>AI preview</span>
                <strong>{analysis ? "Loaded" : "Not run"}</strong>
              </div>

              <div className="summary-card">
                <span>Markdown</span>
                <strong>{markdown ? "Generated" : "Not generated"}</strong>
              </div>
            </div>
          </div>
        </section>

        <aside className="panel">
          <div className="panel-header">
            <div>
              <h2>Admin data</h2>
              <p>Basic manual record management.</p>
            </div>
          </div>

          <div className="section-list">
            {adminSections.map((section) => (
              <button className="section-button" key={section} type="button">
                {section}
              </button>
            ))}
          </div>
        </aside>
      </section>
    </main>
  );
}

export default App;