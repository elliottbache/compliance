function App() {
  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Compliance MVP</p>
          <h1>Inspection Dashboard</h1>
        </div>

        <div className="status-pill">Local demo</div>
      </header>

      <section className="dashboard-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Site workflow</h2>
              <p>Load site history, attachments, AI analysis, and reports.</p>
            </div>
          </div>

          <div className="placeholder-box">
            Site workflow components will go here.
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Admin data</h2>
              <p>Manage core compliance records.</p>
            </div>
          </div>

          <div className="placeholder-box">
            Admin sections will go here.
          </div>
        </section>
      </section>
    </main>
  );
}

export default App;