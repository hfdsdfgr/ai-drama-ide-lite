export function StatusBar() {
  return (
    <footer className="statusbar">
      <span className="statusbar-item">
        <span className="status-dot" aria-hidden="true" />
        就绪
      </span>
      <span className="statusbar-spacer" />
      <span className="statusbar-item statusbar-muted">
        AI Drama IDE Lite v0.1.0
      </span>
    </footer>
  );
}
