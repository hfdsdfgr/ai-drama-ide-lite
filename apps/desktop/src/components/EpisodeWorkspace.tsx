import type {
  EpisodeBlocker,
  EpisodeProduction,
  EpisodeWorkspace as EpisodeWorkspaceData,
  ProductionState,
} from "../types/overview";

const STATUS_LABEL: Record<ProductionState, string> = {
  missing: "缺失",
  ready: "就绪",
  active: "进行中",
  failed: "失败",
  pending: "待审",
  passed: "通过",
  flagged: "异常",
  not_started: "未开始",
  not_referenced: "未引用",
};

function StatusCell({ state, detail }: { state: ProductionState; detail?: string }) {
  return (
    <span
      className={`production-state production-state-${state}`}
      aria-label={detail ? `${STATUS_LABEL[state]}，${detail}` : STATUS_LABEL[state]}
      title={detail}
    >
      <span className="production-state-dot" aria-hidden="true" />
      {detail || STATUS_LABEL[state]}
    </span>
  );
}

function BlockerActions({
  blockers,
  onOpen,
}: {
  blockers: EpisodeBlocker[];
  onOpen: (blocker: EpisodeBlocker) => void;
}) {
  if (blockers.length === 0) return <span className="production-ready">可交付</span>;
  if (blockers.length === 1) {
    return (
      <button
        type="button"
        className="production-issue"
        onClick={() => onOpen(blockers[0])}
      >
        {blockers[0].label}
      </button>
    );
  }
  return (
    <details className="production-issues">
      <summary>
        {blockers[0].label} <span>+{blockers.length - 1}</span>
      </summary>
      <div className="production-issue-list">
        {blockers.map((blocker) => (
          <button key={blocker.code} type="button" onClick={() => onOpen(blocker)}>
            {blocker.label}
          </button>
        ))}
      </div>
    </details>
  );
}

export function EpisodeWorkspace({
  data,
  selectedEpisodeId,
  preparing,
  notice,
  onSelectEpisode,
  onPrepare,
  onJumpToShot,
  onOpenAssets,
}: {
  data: EpisodeWorkspaceData | null;
  selectedEpisodeId: string;
  preparing: boolean;
  notice: string;
  onSelectEpisode: (episodeId: string) => void;
  onPrepare: (episodeId: string) => void;
  onJumpToShot?: (shotId: string) => void;
  onOpenAssets?: () => void;
}) {
  const episodes = data?.episodes ?? [];
  const selected =
    episodes.find((episode) => episode.episode_id === selectedEpisodeId) ?? episodes[0];

  function openBlocker(
    episode: EpisodeProduction,
    blocker: EpisodeBlocker,
    shotId: string,
  ) {
    onSelectEpisode(episode.episode_id);
    if (blocker.target === "assets") onOpenAssets?.();
    else onJumpToShot?.(shotId);
  }

  const progress = selected?.shot_count
    ? Math.round((selected.completed_shots / selected.shot_count) * 100)
    : 0;

  return (
    <section className="episode-workspace" aria-labelledby="episode-workspace-title">
      <div className="episode-workspace-head">
        <div>
          <p className="section-kicker">EPISODE CONTROL</p>
          <h2 id="episode-workspace-title">剧集制作台</h2>
          <p className="muted">从剧本到视频，按镜头定位下一处需要处理的工作。</p>
        </div>
        {selected && (
          <div className="episode-workspace-actions">
            <label>
              <span>剧集</span>
              <select
                value={selected.episode_id}
                onChange={(event) => onSelectEpisode(event.target.value)}
              >
                {episodes.map((episode) => (
                  <option key={episode.episode_id} value={episode.episode_id}>
                    第 {episode.order_index + 1} 集 · {episode.title || "未命名"}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="btn-primary"
              disabled={preparing}
              onClick={() => onPrepare(selected.episode_id)}
            >
              {preparing ? "正在预检…" : "准备本集"}
            </button>
          </div>
        )}
      </div>

      {notice && (
        <p className="episode-prepare-notice" role="status" aria-atomic="true">
          {notice}
        </p>
      )}

      {!selected ? (
        <div className="episode-workspace-empty">
          <p>还没有可制作的剧集。</p>
          <p className="muted">先在「剧本」中创建分集和场景，再回到这里统筹制作。</p>
        </div>
      ) : (
        <>
          <div className="episode-summary" role="status" aria-atomic="true">
            <div className="episode-progress-copy">
              <strong>{progress}%</strong>
              <span>
                {selected.completed_shots}/{selected.shot_count} 个镜头可交付
              </span>
            </div>
            <progress
              value={selected.completed_shots}
              max={Math.max(selected.shot_count, 1)}
            >
              {progress}%
            </progress>
            <div className="episode-summary-meta">
              <span>{selected.scene_count} 场</span>
              <span className={selected.attention_count ? "summary-attention" : ""}>
                {selected.attention_count} 个待处理
              </span>
              {selected.active_count > 0 && <span>{selected.active_count} 个生成中</span>}
            </div>
          </div>

          {selected.shots.length === 0 ? (
            <p className="episode-workspace-empty muted">本集还没有分镜。</p>
          ) : (
            <div className="production-table-wrap">
              <table className="production-table">
                <thead>
                  <tr>
                    <th scope="col">镜头</th>
                    <th scope="col">剧本</th>
                    <th scope="col">资产</th>
                    <th scope="col">提示词</th>
                    <th scope="col">关键帧</th>
                    <th scope="col">视频</th>
                    <th scope="col">审查</th>
                    <th scope="col">下一步</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.shots.map((shot) => {
                    const readyAssets = shot.assets.filter(
                      (asset) => asset.has_image,
                    ).length;
                    const assetDetail = shot.assets.length
                      ? `${readyAssets}/${shot.assets.length}`
                      : undefined;
                    return (
                      <tr key={shot.shot_id}>
                        <th scope="row">
                          <button
                            type="button"
                            className="production-shot-link"
                            onClick={() => onJumpToShot?.(shot.shot_id)}
                          >
                            <span>Shot {shot.shot_number ?? shot.order_index + 1}</span>
                            <small>{shot.scene_title}</small>
                          </button>
                        </th>
                        <td data-label="剧本">
                          <StatusCell state={shot.script_status} />
                        </td>
                        <td data-label="资产">
                          <StatusCell state={shot.asset_status} detail={assetDetail} />
                        </td>
                        <td data-label="提示词">
                          <StatusCell state={shot.prompt_status} />
                        </td>
                        <td data-label="关键帧">
                          <StatusCell state={shot.image_status} />
                        </td>
                        <td data-label="视频">
                          <StatusCell state={shot.video_status} />
                        </td>
                        <td data-label="审查">
                          <StatusCell state={shot.review_status} />
                        </td>
                        <td data-label="下一步">
                          <BlockerActions
                            blockers={shot.blockers}
                            onOpen={(blocker) =>
                              openBlocker(selected, blocker, shot.shot_id)
                            }
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
