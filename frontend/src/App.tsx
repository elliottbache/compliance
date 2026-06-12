import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  type AuthCredentials,
  createSiteAnalysis,
  getSiteAttachments,
  getSiteHistory,
  setAuthCredentialsProvider,
} from "./api/complianceApi";
import { SiteSearchPanel } from "./components/SiteSearchPanel";
import { SiteHistoryPanel } from "./components/SiteHistoryPanel";
import { AttachmentsPanel } from "./components/AttachmentsPanel";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { MarkdownPanel } from "./components/MarkdownPanel";
import { buildSiteAnalysisMarkdown } from "./utils/formatSiteAnalysisMarkdown";
import { getErrorMessage } from "./utils/apiErrors";
import { AdminPanel } from "./components/admin/AdminPanel";
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

type PendingAuthRequest = {
  resolve: (credentials: AuthCredentials | null) => void;
};

type AuthDialogProps = {
  request: PendingAuthRequest | null;
  onCancel: () => void;
  onSubmit: (credentials: AuthCredentials) => void;
};

function AuthDialog({ request, onCancel, onSubmit }: AuthDialogProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (request) {
      setEmail("");
      setPassword("");
    }
  }, [request]);

  if (!request) {
    return null;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onSubmit({ email: email.trim(), password });
  }

  return (
    <div className="auth-backdrop">
      <form
        aria-labelledby="auth-dialog-title"
        aria-modal="true"
        className="auth-dialog"
        role="dialog"
        onSubmit={handleSubmit}
      >
        <div>
          <p className="eyebrow">Authentication</p>
          <h2 id="auth-dialog-title">Sign in</h2>
        </div>

        <label>
          Email
          <input
            autoComplete="username"
            autoFocus
            required
            className="input"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <label>
          Password
          <input
            autoComplete="current-password"
            required
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        <div className="button-row auth-dialog-actions">
          <button className="button button-primary" type="submit">
            Sign in
          </button>
          <button className="button" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function parseSiteId(siteId: string): number {
  const parsed = Number(siteId);

  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error("Enter a valid positive numeric site ID.");
  }

  return parsed;
}

function downloadTextFile(text: string, filename: string): void {
  const blob = new Blob([text], {
    type: "text/markdown;charset=utf-8",
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(url);
}

function App() {
  const [authRequest, setAuthRequest] = useState<PendingAuthRequest | null>(
    null,
  );
  const [siteId, setSiteId] = useState("1");
  const [history, setHistory] = useState<SiteHistory | null>(null);
  const [attachments, setAttachments] = useState<SiteAttachmentsOut | null>(
    null,
  );
  const [analysis, setAnalysis] = useState<SiteAnalysis | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [error, setError] = useState<ApiErrorMessage>(null);
  const [loading, setLoading] = useState<LoadingState>(null);

  useEffect(() => {
    setAuthCredentialsProvider(
      () =>
        new Promise((resolve) => {
          setAuthRequest({ resolve });
        }),
    );

    return () => setAuthCredentialsProvider(null);
  }, []);

  function handleAuthCancel(): void {
    authRequest?.resolve(null);
    setAuthRequest(null);
  }

  function handleAuthSubmit(credentials: AuthCredentials): void {
    authRequest?.resolve(credentials);
    setAuthRequest(null);
  }

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
      setMarkdown("");
    });
  }

  function handleGenerateMarkdown(): void {
    if (!analysis) {
      setError("Run AI Analysis before generating Markdown.");
      return;
    }

    setError(null);
    setMarkdown(buildSiteAnalysisMarkdown(analysis));
  }

  function handleDownloadMarkdown(): void {
    if (!markdown) {
      setError("Generate Markdown before downloading it.");
      return;
    }

    try {
      const parsedSiteId = parseSiteId(siteId);
      downloadTextFile(markdown, `site-${parsedSiteId}-analysis.md`);
      setError(null);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    }
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
      <AuthDialog
        request={authRequest}
        onCancel={handleAuthCancel}
        onSubmit={handleAuthSubmit}
      />

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

      <section className="dashboard-stack">
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
                  {history ? `${history.inspection_count} inspections` : "Not loaded"}
                </strong>
              </div>

              <div className="summary-card">
                <span>Attachments</span>
                <strong>
                  {attachments ? `${attachments.attachments.length} files` : "Not loaded"}
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

            <SiteHistoryPanel history={history} />
            <AttachmentsPanel attachments={attachments} />
            <AnalysisPanel analysis={analysis} />
            <MarkdownPanel
              loading={loading}
              markdown={markdown}
              onDownload={handleDownloadMarkdown}
            />
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Admin data</h2>
              <p>Basic manual record management.</p>
            </div>
          </div>

          <AdminPanel />
        </section>
      </section>
    </main>
  );
}

export default App;
