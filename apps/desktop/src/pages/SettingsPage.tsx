export function SettingsPage() {
  return (
    <div className="page">
      <h2>设置</h2>
      <div className="card">
        <h3>AI Provider</h3>
        <p className="muted">
          Provider 配置（LLM / Image / Video）将在 Phase 3（AI Provider
          基础系统）实现。
        </p>
      </div>
      <div className="card">
        <h3>应用</h3>
        <p className="muted">环境变量、日志等系统设置将随各阶段逐步开放。</p>
      </div>
    </div>
  );
}
