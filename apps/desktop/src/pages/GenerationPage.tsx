import { useCallback, useEffect, useRef, useState } from "react";

import {
  listJobs,
  cancelJob,
  pauseJob,
  retryJob,
  resumeJob,
  batchJobs,
} from "../api/jobs";
import { getProjectOverview } from "../api/overview";
import { getProjectQuality, type ProjectQuality } from "../api/quality";
import { listProjects } from "../api/projects";
import type { JobOut, JobStatus } from "../types/job";
import type { ProjectOverview, StageStatus } from "../types/overview";
import type { Project } from "../types/project";

const STATUS_LABEL: Record<JobStatus, string> = {
  queued: "排队中",
  running: "生成中",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const CAPABILITY_LABEL: Record<string, string> = {
  text_to_image: "文生图",
  image_to_image: "图生图",
  reference_image: "参考图",
  character_reference: "角色参考",
  text_to_video: "文生视频",
  image_to_video: "图生视频",
  video_to_video: "视频生视频",
  llm_asset_completion: "资产卡补全",
  lip_sync: "口型同步",
  text_to_speech: "语音合成",
  audio_separation: "人声分离",
  audio_mix: "混音",
  dialogue_review: "台词审核",
  visual_review: "视觉一致性检查",
};

const JOB_STAGE_LABEL: Record<string, string> = {
  queued: "排队中",
  running: "生成中",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const STAGE_ICON: Record<StageStatus, string> = {
  pending: "○",
  active: "●",
  completed: "✓",
};

type Filter = "all" | "active" | "completed" | "failed";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "active", label: "进行中" },
  { key: "completed", label: "已完成" },
  { key: "failed", label: "失败" },
];

function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function matchesFilter(job: JobOut, filter: Filter): boolean {
  if (filter === "all") return true;
  if (filter === "active") {
    return job.status === "queued" || job.status === "running" || job.status === "paused";
  }
  return job.status === filter;
}

export function GenerationPage({
  active,
  onJumpToShot,
}: {
  active: boolean;
  onJumpToShot?: (shotId: string) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [quality, setQuality] = useState<ProjectQuality | null>(null);
  const [jobs, setJobs] = useState<JobOut[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [cancelArmed, setCancelArmed] = useState<Record<string, boolean>>({});
  const [batchArmed, setBatchArmed] = useState(false);
  const [stageArmed, setStageArmed] = useState<Record<string, boolean>>({});
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    listProjects()
      .then((ps) => {
        setProjects(ps);
        setProjectId((prev) =>
          prev && ps.some((p) => p.id === prev) ? prev : (ps[0]?.id ?? ""),
        );
      })
      .catch((e) => setError((e as Error).message));
  }, []);

  const refresh = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [nextOverview, nextJobs, nextQuality] = await Promise.all([
        getProjectOverview(projectId),
        listJobs({ project_id: projectId, limit: 200 }),
        getProjectQuality(projectId),
      ]);
      setOverview(nextOverview);
      setJobs(nextJobs);
      setQuality(nextQuality);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!active || !projectId) return;
    void refresh();
    timerRef.current = window.setInterval(() => {
      void refresh();
    }, 3000);
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [active, projectId, refresh]);

  const visible = jobs.filter((job) => matchesFilter(job, filter));
  const flaggedItems = (quality?.items ?? []).filter(
    (item) => item.status === "flagged",
  );
  const pendingItems = (quality?.items ?? []).filter(
    (item) => item.status === "pending",
  );

  async function handleCancel(job: JobOut) {
    if (!cancelArmed[job.job_id]) {
      setCancelArmed((prev) => ({ ...prev, [job.job_id]: true }));
      window.setTimeout(() => {
        setCancelArmed((prev) => ({ ...prev, [job.job_id]: false }));
      }, 3000);
      return;
    }
    try {
      await cancelJob(job.job_id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleRetry(job: JobOut) {
    try {
      await retryJob(job.job_id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleResume(job: JobOut) {
    try {
      await resumeJob(job.job_id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handlePause(job: JobOut) {
    try {
      await pauseJob(job.job_id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleBatch(action: "pause" | "resume" | "cancel") {
    if (!projectId) return;
    if (action === "cancel" && !batchArmed) {
      setBatchArmed(true);
      window.setTimeout(() => setBatchArmed(false), 3000);
      return;
    }
    try {
      await batchJobs({ project_id: projectId, action });
      setBatchArmed(false);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleCancelStage(stageKey: string) {
    if (!projectId) return;
    if (!stageArmed[stageKey]) {
      setStageArmed((prev) => ({ ...prev, [stageKey]: true }));
      window.setTimeout(() => {
        setStageArmed((prev) => ({ ...prev, [stageKey]: false }));
      }, 3000);
      return;
    }
    try {
      await batchJobs({
        project_id: projectId,
        action: "cancel",
        stage: stageKey,
      });
      setStageArmed((prev) => ({ ...prev, [stageKey]: false }));
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>生成中心</h2>
          <p className="muted">查看当前项目从小说到成片的整体进度，以及正在执行的生成任务。</p>
        </div>
      </div>

      <div className="toolbar">
        <label className="project-picker">
          项目
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            disabled={projects.length === 0}
          >
            {projects.length === 0 && <option value="">暂无项目</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => void refresh()} disabled={loading || !projectId}>
          {loading ? "刷新中…" : "刷新"}
        </button>
        <button
          type="button"
          onClick={() => void handleBatch("pause")}
          disabled={loading || !projectId}
        >
          暂停全部
        </button>
        <button
          type="button"
          onClick={() => void handleBatch("resume")}
          disabled={loading || !projectId}
        >
          恢复全部
        </button>
        <button
          type="button"
          className={batchArmed ? "button-danger" : "button-ghost"}
          onClick={() => void handleBatch("cancel")}
          disabled={loading || !projectId}
        >
          {batchArmed ? "确认停止全部" : "停止全部"}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {projects.length === 0 ? (
        <div className="card">
          <p className="muted">还没有项目，请先到主页创建一个项目。</p>
        </div>
      ) : (
        <div className="generation-layout">
          <section className="card overview-panel">
            <h3>生产进度</h3>
            <ol className="overview-stepper">
              {(overview?.stages ?? []).map((stage) => (
                <li
                  key={stage.key}
                  className={`overview-step overview-step-${stage.status}`}
                >
                  <span className="overview-step-icon" aria-hidden="true">
                    {STAGE_ICON[stage.status]}
                  </span>
                  <span className="overview-step-text">
                    <span className="overview-step-label">{stage.label}</span>
                    {stage.detail && (
                      <span className="overview-step-detail">{stage.detail}</span>
                    )}
                  </span>
                  {stage.status === "active" && stage.jobs.length > 0 && (
                    <>
                      <ul className="stage-jobs">
                        {stage.jobs.map((job) => (
                          <li key={job.job_id} className="stage-job">
                            <span
                              className={`stage-job-dot stage-job-${job.status}`}
                              aria-hidden="true"
                            />
                            <span className="stage-job-text">
                              {CAPABILITY_LABEL[job.capability] ?? job.capability}
                              {job.target_label ? ` · ${job.target_label}` : ""}
                            </span>
                            {job.status === "running" ? (
                              job.progress > 0 ? (
                                <span className="stage-job-progress">
                                  {job.progress}%
                                </span>
                              ) : (
                                <span className="muted">处理中…</span>
                              )
                            ) : (
                              <span className="stage-job-progress">
                                {JOB_STAGE_LABEL[job.status] ?? job.status}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                      <button
                        type="button"
                        className={`stage-stop ${stageArmed[stage.key] ? "button-danger" : "button-ghost"}`}
                        onClick={() => void handleCancelStage(stage.key)}
                      >
                        {stageArmed[stage.key] ? "确认停止该阶段" : "停止该阶段"}
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ol>
          </section>

          <section className="generation-jobs">
            <section className="card quality-panel">
              <div className="quality-head">
                <h3>质量报告</h3>
                <div className="quality-summary">
                  <span className="quality-bad">
                    异常 {quality?.summary.flagged ?? 0}
                  </span>
                  <span className="quality-muted">
                    待审核 {quality?.summary.pending ?? 0}
                  </span>
                  <span className="quality-good">
                    通过 {quality?.summary.passed ?? 0}
                  </span>
                </div>
              </div>
              {flaggedItems.length === 0 && pendingItems.length === 0 ? (
                <p className="muted">
                  还没有分镜审核记录，去分镜页对镜头做台词 / 视觉一致性检查。
                </p>
              ) : (
                <div className="quality-lists">
                  {flaggedItems.length > 0 && (
                    <div>
                      <h4>异常镜头</h4>
                      <ul className="quality-list">
                        {flaggedItems.map((item) => (
                          <li
                            key={item.shot_id}
                            className="quality-item quality-item-flagged"
                            onClick={() => onJumpToShot?.(item.shot_id)}
                            title="点击跳转到该分镜"
                          >
                            <span className="quality-shot">
                              {item.scene_title || "未命名场景"} · Shot{" "}
                              {item.shot_number ?? ""}
                            </span>
                            <span className="quality-issue">
                              {item.reviews
                                .filter((r) => r.status === "flagged")
                                .map((r) => r.issue || "审核异常")
                                .join("；")}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {pendingItems.length > 0 && (
                    <div>
                      <h4>待审核镜头</h4>
                      <ul className="quality-list">
                        {pendingItems.map((item) => (
                          <li
                            key={item.shot_id}
                            className="quality-item quality-item-pending"
                            onClick={() => onJumpToShot?.(item.shot_id)}
                            title="点击跳转到该分镜"
                          >
                            <span className="quality-shot">
                              {item.scene_title || "未命名场景"} · Shot{" "}
                              {item.shot_number ?? ""}
                            </span>
                            <span className="quality-issue">尚未审核</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </section>
            <div className="toolbar">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  className={filter === f.key ? "nav-active" : ""}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {visible.length === 0 ? (
              <div className="card">
                <p className="muted">该分类下没有任务。</p>
              </div>
            ) : (
              <div className="jobs-list">
                {visible.map((job) => (
                  <div className="card job-row" key={job.job_id}>
                    <div className="job-main">
                      <span className={`job-status job-status-${job.status}`}>
                        {STATUS_LABEL[job.status]}
                      </span>
                      <span className="job-title">
                        {CAPABILITY_LABEL[job.capability] ?? job.capability ?? job.type}
                      </span>
                    </div>
                    {job.error && (
                      <p className="job-error">
                        {job.error}
                        {job.error_category === "retryable" && "（可重试）"}
                      </p>
                    )}
                    {job.status === "running" && (
                      <div className="progress-bar">
                        <div
                          className="progress-bar-fill"
                          style={{
                            width:
                              job.progress > 0
                                ? `${Math.min(job.progress, 100)}%`
                                : "8%",
                            opacity: job.progress > 0 ? 1 : 0.4,
                          }}
                        />
                      </div>
                    )}
                    <div className="job-meta">
                      <span className="muted">
                        创建于 {formatTime(job.created_at)}
                        {job.completed_at && ` · 结束于 ${formatTime(job.completed_at)}`}
                      </span>
                      {job.status === "running" && job.progress > 0 && (
                        <span className="muted">进度 {job.progress}%</span>
                      )}
                    </div>
                    <div className="job-actions">
                      {job.status === "running" && (
                        <button type="button" onClick={() => void handlePause(job)}>
                          暂停
                        </button>
                      )}
                      {job.status === "paused" && (
                        <button type="button" onClick={() => void handleResume(job)}>
                          恢复
                        </button>
                      )}
                      {(job.status === "queued" ||
                        job.status === "running" ||
                        job.status === "paused") && (
                        <button
                          type="button"
                          className={cancelArmed[job.job_id] ? "button-danger" : "button-ghost"}
                          onClick={() => void handleCancel(job)}
                        >
                          {cancelArmed[job.job_id] ? "确认取消" : "取消"}
                        </button>
                      )}
                      {(job.status === "failed" || job.status === "cancelled") && (
                        <button type="button" onClick={() => void handleRetry(job)}>
                          重试
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
