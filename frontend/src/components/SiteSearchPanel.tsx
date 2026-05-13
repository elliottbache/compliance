import type { LoadingState } from "../types";

type SiteSearchPanelProps = {
  siteId: string;
  loading: LoadingState;
  onSiteIdChange: (siteId: string) => void;
  onLoadHistory: () => void;
  onLoadAttachments: () => void;
  onRunAnalysis: () => void;
  onGenerateMarkdown: () => void;
  onClear: () => void;
};

function isLoadingAction(loading: LoadingState, action: string): boolean {
  return loading === action;
}

export function SiteSearchPanel({
  siteId,
  loading,
  onSiteIdChange,
  onLoadHistory,
  onLoadAttachments,
  onRunAnalysis,
  onGenerateMarkdown,
  onClear,
}: SiteSearchPanelProps) {
  const isBusy = loading !== null;

  return (
    <section className="workflow-card">
      <div className="site-control">
        <label htmlFor="site-id">Site ID</label>
        <input
          className="input site-id-input"
          id="site-id"
          inputMode="numeric"
          min="1"
          type="number"
          value={siteId}
          onChange={(event) => onSiteIdChange(event.target.value)}
        />
      </div>

      <div className="button-row">
        <button
          className="button"
          disabled={isBusy}
          type="button"
          onClick={onLoadHistory}
        >
          {isLoadingAction(loading, "history") ? "Loading..." : "Load History"}
        </button>

        <button
          className="button"
          disabled={isBusy}
          type="button"
          onClick={onLoadAttachments}
        >
          {isLoadingAction(loading, "attachments")
            ? "Loading..."
            : "Load Attachments"}
        </button>

        <button
          className="button button-primary"
          disabled={isBusy}
          type="button"
          onClick={onRunAnalysis}
        >
          {isLoadingAction(loading, "analysis")
            ? "Running..."
            : "Run AI Analysis"}
        </button>

        <button
          className="button"
          disabled={isBusy}
          type="button"
          onClick={onGenerateMarkdown}
        >
          {isLoadingAction(loading, "markdown")
            ? "Generating..."
            : "Generate Markdown"}
        </button>

        <button
          className="button"
          disabled={isBusy}
          type="button"
          onClick={onClear}
        >
          Clear
        </button>
      </div>

      {loading ? (
        <p className="loading-text">Current action: {loading}</p>
      ) : null}

      <p className="helper-text">
        AI calls only run when you click the "Run AI Analysis" buttons.
      </p>
    </section>
  );
}