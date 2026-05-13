import type { LoadingState } from "../types";

type MarkdownPanelProps = {
  markdown: string;
  loading: LoadingState;
  onDownload: () => void;
};

export function MarkdownPanel({
  markdown,
  loading,
  onDownload,
}: MarkdownPanelProps) {
  const isDownloading = loading === "markdown-download";

  if (!markdown) {
    return (
      <section className="result-panel">
        <div className="result-panel-header">
          <div>
            <h3>Markdown report</h3>
            <p>Generate Markdown to preview the draft report text.</p>
          </div>

          <button
            className="button"
            disabled={loading !== null}
            type="button"
            onClick={onDownload}
          >
            {isDownloading ? "Downloading..." : "Download Markdown"}
          </button>
        </div>

        <div className="empty-state">No Markdown report generated.</div>
      </section>
    );
  }

  return (
    <section className="result-panel">
      <div className="result-panel-header">
        <div>
          <h3>Markdown report</h3>
          <p>Draft report text. Human review required before use.</p>
        </div>

        <button
          className="button"
          disabled={loading !== null}
          type="button"
          onClick={onDownload}
        >
          {isDownloading ? "Downloading..." : "Download Markdown"}
        </button>
      </div>

      <textarea
        className="textarea markdown-textarea"
        readOnly
        value={markdown}
      />
    </section>
  );
}