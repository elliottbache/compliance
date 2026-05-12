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

function App() {
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

          <div className="placeholder-box">
            Site workflow components will go here.
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