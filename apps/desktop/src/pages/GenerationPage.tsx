import { useCallback, useEffect, useRef, useState } from "react";

import { listJobs, cancelJob, retryJob, resumeJob } from "../api/jobs";
import { getProjectOverview } from "../api/overview";
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
  llm_asset_completion: "资产卡补全",
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

export function GenerationPage({ active }: { active: boolean }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [jobs, setJobs] = useState<JobOut[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [cancelArmed, setCancelArmed] = useState<Record<string, boolean>>({});
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
      const [nextOverview, nextJobs] = await Promise.all([
        getProjectOverview(projectId),
        listJobs({ project_id: projectId, limit: 200 }),
      ]);
      setOverview(nextOverview);
      setJobs(nextJobs);
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
                </li>
              ))}
            </ol>
          </section>

          <section className="generation-jobs">
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
                <p className="muted">
                  {filter === "all"
                    ? "该分类下没有任务。"
                    : "该分类下没有任务。"}
                </p>
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
