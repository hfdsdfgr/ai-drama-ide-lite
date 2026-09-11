import { useEffect, useState } from "react";
import {
  getDependencyView,
  type DependencyViewNode,
  type DependencyViewResponse,
} from "../api/production_graph";

const STATE_LABEL: Record<string, string> = {
  none: "无外部来源",
  current: "当前版本",
  stale: "待确认",
  pinned: "沿用指定版",
  unknown: "来源待核实",
  broken: "来源失效",
};

export type DependencyScope = { shotId: string } | { sceneId: string };

const PAGE_SIZE = 20;

export function DependencyView({
  projectId,
  scope,
  onClose,
  onJumpToShot,
  onOpenAssets,
}: {
  projectId: string;
  scope: DependencyScope;
  onClose: () => void;
  onJumpToShot?: (shotId: string, media?: "image" | "video") => void;
  onOpenAssets?: (assetId?: string) => void;
}) {
  const [data, setData] = useState<DependencyViewResponse | null>(null);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);

  const shotId = "shotId" in scope ? scope.shotId : undefined;
  const sceneId = "sceneId" in scope ? scope.sceneId : undefined;
  const scopeKey = shotId ? `shot:${shotId}` : `scene:${sceneId}`;

  useEffect(() => setOffset(0), [scopeKey]);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    getDependencyView(projectId, shotId ? { shotId } : { sceneId: sceneId! }, {
      limit: PAGE_SIZE,
      offset,
    })
      .then((next) => !cancelled && setData(next))
      .catch((reason: Error) => !cancelled && setError(reason.message));
    return () => {
      cancelled = true;
    };
  }, [projectId, shotId, sceneId, offset]);

  function open(node: DependencyViewNode) {
    if (node.target.type === "asset") onOpenAssets?.(node.target.id);
    if (node.target.type === "shot" && node.target.id) {
      onJumpToShot?.(node.target.id, node.target.media);
    }
  }

  return (
    <section className="card dependency-view" aria-labelledby="dependency-view-title">
      <div className="dependency-view-head">
        <div>
          <h3 id="dependency-view-title">版本依赖</h3>
          <p className="muted">
            展示当前{data?.scope.type === "scene" ? "场景" : "镜头"}
            结果实际使用的参考版本。
          </p>
        </div>
        <button type="button" onClick={onClose}>
          关闭
        </button>
      </div>
      {!data && !error && <p className="muted">正在读取依赖…</p>}
      {error && <p className="error">{error}</p>}
      {data?.shots.map((shot) => {
        const nodes = new Map(shot.nodes.map((node) => [node.id, node]));
        return (
          <div className="dependency-shot" key={shot.shot_id}>
            <strong>{shot.label}</strong>
            {shot.edges.length ? (
              <div className="dependency-edge-list">
                {shot.edges.map((edge, index) => (
                  <div
                    className="dependency-edge"
                    key={`${edge.source}-${edge.target}-${index}`}
                  >
                    <Node node={nodes.get(edge.source)} onOpen={open} />
                    <span aria-hidden="true">→</span>
                    <Node node={nodes.get(edge.target)} onOpen={open} />
                  </div>
                ))}
              </div>
            ) : shot.nodes.length ? (
              <div className="dependency-edge-list">
                {shot.nodes.map((node) => (
                  <Node key={node.id} node={node} onOpen={open} />
                ))}
              </div>
            ) : (
              <p className="muted">这个镜头还没有可追踪的生成版本。</p>
            )}
            {!!shot.issues.length && (
              <details className="dependency-view-issues">
                <summary>{shot.issues.length} 个依赖说明</summary>
                <ul>
                  {shot.issues.map((issue, index) => (
                    <li key={`${issue.media}-${index}`}>{issue.label}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        );
      })}
      {data && data.scope.type === "scene" && data.total > PAGE_SIZE && (
        <div className="dependency-pagination" aria-label="场景依赖分页">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            上一页
          </button>
          <span>
            {offset + 1}–{Math.min(offset + data.shots.length, data.total)} / {data.total}
          </span>
          <button
            type="button"
            disabled={offset + data.shots.length >= data.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            下一页
          </button>
        </div>
      )}
    </section>
  );
}

function Node({
  node,
  onOpen,
}: {
  node?: DependencyViewNode;
  onOpen: (node: DependencyViewNode) => void;
}) {
  if (!node)
    return <span className="dependency-node dependency-node-broken">未知来源</span>;
  const content = (
    <>
      <strong>
        {node.label}
        {node.version ? ` v${node.version}` : ""}
      </strong>
      <small>
        {STATE_LABEL[node.state] ?? node.state}
        {node.current_version && node.current_version !== node.version
          ? ` · 当前 v${node.current_version}`
          : ""}
      </small>
    </>
  );
  return node.target.type ? (
    <button
      type="button"
      className={`dependency-node dependency-node-${node.state}`}
      onClick={() => onOpen(node)}
    >
      {content}
    </button>
  ) : (
    <span className={`dependency-node dependency-node-${node.state}`}>{content}</span>
  );
}
