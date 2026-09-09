import { useCallback, useEffect, useRef, useState } from "react";

import {
  listJobs,
  cancelJob,
  pauseJob,
  retryJob,
  resumeJob,
  batchJobs,
  getJob,
  getProjectJobState,
} from "../api/jobs";
import { getProjectOverview } from "../api/overview";
import { getProjectQuality, type ProjectQuality } from "../api/quality";
import {
  getPipelinePlan,
  getPipelineStatus,
  startPipeline,
  type PipelinePlan,
  type PipelineStatus,
} from "../api/pipeline";
import type { JobOut, JobStatus } from "../types/job";
import type { ProjectOverview, StageStatus } from "../types/overview";

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
  story_review: "剧情一致性检查",
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

const STAGE_LABELS: Record<string, string> = {
  novel_analysis: "小说分析 / 故事圣经",
  script: "剧本生成（分集 / 场景）",
  assets: "资产卡补全",
  storyboard: "分镜生成",
  shot_images: "分镜图生成",
  videos: "图生视频",
  quality_review: "质量审查（视觉/剧情/台词）",
};

const PIPELINE_STATUS_LABEL: Record<string, string> = {
  queued: "排队中",
  running: "生成中",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
};

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

function groupBatchJobs(jobs: JobOut[]) {
  const groups = new Map<string, { id: string; label: string; jobs: JobOut[] }>();
  for (const job of jobs) {
    if (!job.batch_id) continue;
    const group = groups.get(job.batch_id) ?? {
      id: job.batch_id,
      label: job.batch_label || "批量关键帧",
      jobs: [],
    };
    group.jobs.push(job);
    groups.set(job.batch_id, group);
  }
  return [...groups.values()];
}

function JobRow({
  job,
  cancelArmed,
  resumeArmed,
  onCancel,
  onPause,
  onResume,
  onRetry,
  onJumpToShot,
}: {
  job: JobOut;
  cancelArmed: boolean;
  resumeArmed: boolean;
  onCancel: (job: JobOut) => void;
  onPause: (job: JobOut) => void;
  onResume: (job: JobOut) => void;
  onRetry: (job: JobOut) => void;
  onJumpToShot?: (shotId: string) => void;
}) {
  const interrupted = job.error_category === "interrupted";
  return (
    <div className="card job-row">
      <div className="job-main">
        <span className={`job-status job-status-${job.status}`}>
          {STATUS_LABEL[job.status]}
        </span>
        <span className="job-title">
          {job.target_label || CAPABILITY_LABEL[job.capability] || job.type}
        </span>
      </div>
      {job.error && (
        <p className={interrupted ? "job-recovery" : "job-error"}>
          {job.error}
          {job.error_category === "retryable" && "（可重试）"}
          {interrupted &&
            (job.has_remote_task
              ? "。恢复后只会继续查询原厂商任务，不会重新提交"
              : "。恢复会重新向模型提交，可能再次产生费用")}
        </p>
      )}
      {job.status === "running" && (
        <div className="progress-bar" aria-label="任务进度">
          <div
            className="progress-bar-fill"
            style={{
              width: job.progress > 0 ? `${Math.min(job.progress, 100)}%` : "8%",
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
        {job.status === "running" && (
          <span className="muted">
            {job.progress > 0 ? `进度 ${job.progress}%` : "处理中…"}
          </span>
        )}
      </div>
      <div className="job-actions">
        {job.target_id && onJumpToShot && (
          <button type="button" onClick={() => onJumpToShot(job.target_id)}>
            查看分镜
          </button>
        )}
        {job.status === "running" && (
          <button type="button" onClick={() => onPause(job)}>
            暂停
          </button>
        )}
        {job.status === "paused" && (
          <button type="button" onClick={() => onResume(job)}>
            {interrupted
              ? job.has_remote_task
                ? "继续跟踪原任务"
                : resumeArmed
                  ? "确认重新提交"
                  : "重新提交（可能计费）"
              : "恢复"}
          </button>
        )}
        {(["queued", "running", "paused"] as JobStatus[]).includes(job.status) && (
          <button
            type="button"
            className={cancelArmed ? "button-danger" : "button-ghost"}
            onClick={() => onCancel(job)}
          >
            {cancelArmed ? "确认取消" : "取消"}
          </button>
        )}
        {(job.status === "failed" || job.status === "cancelled") && (
          <button type="button" onClick={() => onRetry(job)}>
            重试
          </button>
        )}
      </div>
    </div>
  );
}

export function GenerationPage({
  active,
  projectId,
  onJumpToShot,
}: {
  active: boolean;
  projectId: string;
  onJumpToShot?: (shotId: string) => void;
}) {
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [quality, setQuality] = useState<ProjectQuality | null>(null);
  const [pipelinePlan, setPipelinePlan] = useState<PipelinePlan | null>(null);
  const [planOpen, setPlanOpen] = useState(false);
  const [includeVideos, setIncludeVideos] = useState(false);
  const [autoContinue, setAutoContinue] = useState(false);
  const [qualityReview, setQualityReview] = useState(false);
  const [pipelineJob, setPipelineJob] = useState<JobOut | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const pipelinePollRef = useRef<number | null>(null);
  const [jobs, setJobs] = useState<JobOut[]>([]);
  const [projectPaused, setProjectPaused] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [cancelArmed, setCancelArmed] = useState<Record<string, boolean>>({});
  const [resumeArmed, setResumeArmed] = useState<Record<string, boolean>>({});
  const [batchArmed, setBatchArmed] = useState(false);
  const [batchActionArmed, setBatchActionArmed] = useState<Record<string, boolean>>({});
  const [batchNotice, setBatchNotice] = useState("");
  const [stageArmed, setStageArmed] = useState<Record<string, boolean>>({});
  const jobsRef = useRef<JobOut[]>([]);

  useEffect(() => {
    setOverview(null);
    setQuality(null);
    setPipelinePlan(null);
    setPipelineJob(null);
    setPipelineStatus(null);
    setJobs([]);
    setProjectPaused(false);
    jobsRef.current = [];
    setError("");
    setBatchNotice("");
  }, [projectId]);

  const refresh = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [nextOverview, nextJobs, nextQuality, nextProjectState] = await Promise.all([
        getProjectOverview(projectId),
        listJobs({ project_id: projectId, limit: 200 }),
        getProjectQuality(projectId),
        getProjectJobState(projectId),
      ]);
      setOverview(nextOverview);
      setJobs(nextJobs);
      jobsRef.current = nextJobs;
      setQuality(nextQuality);
      setProjectPaused(nextProjectState.paused);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (!active || !projectId) return;
    let cancelled = false;
    let timeout: number | null = null;
    const tick = async () => {
      await refresh();
      if (cancelled) return;
      const hasActive = jobsRef.current.some((job) =>
        ["queued", "running", "paused"].includes(job.status),
      );
      timeout = window.setTimeout(() => void tick(), hasActive ? 3000 : 15000);
    };
    void tick();
    return () => {
      cancelled = true;
      if (timeout !== null) window.clearTimeout(timeout);
    };
  }, [active, projectId, refresh]);

  const visible = jobs.filter((job) => matchesFilter(job, filter));
  const batchGroups = groupBatchJobs(jobs).filter((group) =>
    group.jobs.some((job) => matchesFilter(job, filter)),
  );
  const unbatchedVisible = visible.filter((job) => !job.batch_id);
  const flaggedItems = (quality?.items ?? []).filter((item) => item.status === "flagged");
  const pendingItems = (quality?.items ?? []).filter((item) => item.status === "pending");

  const currentPipelineStage = (pipelineStatus?.stages ?? []).find(
    (stage) => stage.status === "running" || stage.status === "failed",
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
    if (
      job.error_category === "interrupted" &&
      !job.has_remote_task &&
      !resumeArmed[job.job_id]
    ) {
      setResumeArmed((prev) => ({ ...prev, [job.job_id]: true }));
      window.setTimeout(() => {
        setResumeArmed((prev) => ({ ...prev, [job.job_id]: false }));
      }, 4000);
      return;
    }
    try {
      await resumeJob(job.job_id);
      setResumeArmed((prev) => ({ ...prev, [job.job_id]: false }));
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

  async function handleProductionBatch(
    batchId: string,
    action: "pause" | "resume" | "cancel" | "retry",
  ) {
    if (!projectId) return;
    if (action === "cancel" && !batchActionArmed[batchId]) {
      setBatchActionArmed((prev) => ({ ...prev, [batchId]: true }));
      window.setTimeout(() => {
        setBatchActionArmed((prev) => ({ ...prev, [batchId]: false }));
      }, 3000);
      return;
    }
    try {
      const result = await batchJobs({
        project_id: projectId,
        batch_id: batchId,
        action,
      });
      setBatchActionArmed((prev) => ({ ...prev, [batchId]: false }));
      setBatchNotice(
        `${action === "pause" ? "已暂停" : action === "resume" ? "已恢复" : action === "cancel" ? "已停止" : "已重新排队"} ${result.affected} 个任务。`,
      );
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

  async function openPipelinePlan() {
    if (!projectId) return;
    setError("");
    try {
      const plan = await getPipelinePlan(projectId);
      setPipelinePlan(plan);
      setPlanOpen(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleStartPipeline() {
    if (!projectId) return;
    setError("");
    try {
      const job = await startPipeline(projectId, {
        auto_continue: autoContinue,
        include_videos: includeVideos,
        quality_review: qualityReview,
      });
      setPlanOpen(false);
      setPipelineJob(job);
      await refreshPipeline();
      if (pipelinePollRef.current !== null) {
        window.clearInterval(pipelinePollRef.current);
      }
      pipelinePollRef.current = window.setInterval(() => {
        void refreshPipeline();
      }, 2500);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function refreshPipeline() {
    if (!projectId || !pipelineJob) return;
    try {
      const [job, status] = await Promise.all([
        getJob(pipelineJob.job_id),
        getPipelineStatus(projectId),
      ]);
      setPipelineJob(job);
      setPipelineStatus(status);
      if (["completed", "failed", "cancelled"].includes(job.status)) {
        if (pipelinePollRef.current !== null) {
          window.clearInterval(pipelinePollRef.current);
          pipelinePollRef.current = null;
        }
        if (job.status === "failed" && job.error) setError(job.error);
        // 结束后刷新计划，展示已完成状态
        try {
          setPipelinePlan(await getPipelinePlan(projectId));
        } catch {
          /* 忽略 */
        }
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleResumePipeline() {
    if (!pipelineJob) return;
    setError("");
    try {
      const updated = await resumeJob(pipelineJob.job_id);
      setPipelineJob(updated);
      if (pipelinePollRef.current === null) {
        pipelinePollRef.current = window.setInterval(() => {
          void refreshPipeline();
        }, 2500);
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleStopPipeline() {
    if (!pipelineJob) return;
    setError("");
    try {
      const updated = await cancelJob(pipelineJob.job_id);
      setPipelineJob(updated);
      if (pipelinePollRef.current !== null) {
        window.clearInterval(pipelinePollRef.current);
        pipelinePollRef.current = null;
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>生成中心</h2>
          <p className="muted">
            查看当前项目从小说到成片的整体进度，以及正在执行的生成任务。
          </p>
        </div>
      </div>

      <div className="toolbar">
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading || !projectId}
        >
          {loading ? "刷新中…" : "刷新"}
        </button>
        <button
          type="button"
          onClick={() => void handleBatch("pause")}
          disabled={loading || !projectId || projectPaused}
        >
          暂停全部
        </button>
        <button
          type="button"
          onClick={() => void handleBatch("resume")}
          disabled={loading || !projectId || !projectPaused}
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
      {projectPaused && (
        <p className="project-pause-notice" role="status">
          项目已暂停。当前任务和之后新建的任务都会保持暂停，点击“恢复全部”后继续；意外中断任务仍需逐项确认。
        </p>
      )}

      {!projectId ? (
        <div className="card">
          <p className="muted">先在「主页」打开项目，再查看生成进度。</p>
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
            <section className="card pipeline-panel">
              <div className="quality-head">
                <h3>一键生成（End-to-End）</h3>
                {!pipelineJob && (
                  <button type="button" onClick={() => void openPipelinePlan()}>
                    生成漫剧
                  </button>
                )}
              </div>
              {planOpen && pipelinePlan && (
                <div className="pipeline-plan">
                  {pipelinePlan.stages.map((stage) => (
                    <div
                      key={stage.key}
                      className={`pipeline-stage pipeline-stage-${stage.status}`}
                    >
                      <span className="pipeline-stage-label">{stage.label}</span>
                      {stage.status === "completed" && (
                        <span className="quality-good">已完成</span>
                      )}
                      {stage.status === "ready" && (
                        <span className="quality-muted">将使用 {stage.model_id}</span>
                      )}
                      {stage.status === "not_ready" && (
                        <span className="pipeline-missing">⚠ {stage.missing_reason}</span>
                      )}
                    </div>
                  ))}
                  <label>
                    <input
                      type="checkbox"
                      checked={includeVideos}
                      onChange={(e) => setIncludeVideos(e.target.checked)}
                    />
                    包含视频生成（费用较高，默认关闭）
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={autoContinue}
                      onChange={(e) => setAutoContinue(e.target.checked)}
                    />
                    自动继续（每阶段不停顿等确认）
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={qualityReview}
                      onChange={(e) => setQualityReview(e.target.checked)}
                    />
                    包含质量审查（生成后自动检查视觉/剧情一致性）
                  </label>
                  {qualityReview && (
                    <p className="pipeline-missing">
                      ⚠ 质量审查会对每个分镜调用视觉 / 文本（含视频时还会调用语音转写）
                      模型 API，按镜头逐项审核，会产生明显费用，请确认后勾选。
                    </p>
                  )}
                  <div className="review-actions">
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={!pipelinePlan.can_start}
                      onClick={() => void handleStartPipeline()}
                    >
                      开始生成
                    </button>
                    <button
                      type="button"
                      className="button-ghost"
                      onClick={() => setPlanOpen(false)}
                    >
                      取消
                    </button>
                  </div>
                  {!pipelinePlan.can_start && (
                    <p className="muted">请先在「设置」配置缺失的模型后再开始。</p>
                  )}
                </div>
              )}
              {pipelineJob && (
                <div className="pipeline-run">
                  <p className="muted">
                    状态：{STATUS_LABEL[pipelineJob.status]}
                    {currentPipelineStage && (
                      <>
                        {" "}
                        · 当前阶段：
                        {STAGE_LABELS[currentPipelineStage.stage_key] ??
                          currentPipelineStage.stage_key}
                      </>
                    )}
                  </p>
                  {(pipelineStatus?.stages ?? []).map((stage) => (
                    <div
                      key={stage.stage_key}
                      className={`pipeline-stage pipeline-stage-${stage.status}`}
                    >
                      <span className="pipeline-stage-label">
                        {STAGE_LABELS[stage.stage_key] ?? stage.stage_key}
                      </span>
                      <span className="quality-muted">
                        {PIPELINE_STATUS_LABEL[stage.status] ?? stage.status}
                      </span>
                      {stage.message && (
                        <span className="pipeline-message">{stage.message}</span>
                      )}
                    </div>
                  ))}
                  <div className="review-actions">
                    {pipelineJob.status === "paused" && (
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => void handleResumePipeline()}
                      >
                        继续下一阶段
                      </button>
                    )}
                    {["queued", "running", "paused"].includes(pipelineJob.status) && (
                      <button
                        type="button"
                        className="button-danger button-ghost"
                        onClick={() => void handleStopPipeline()}
                      >
                        停止
                      </button>
                    )}
                    {pipelineJob.status === "completed" && (
                      <span className="quality-good">全部阶段已完成 ✓</span>
                    )}
                  </div>
                </div>
              )}
            </section>
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

            {batchNotice && <p className="notice">{batchNotice}</p>}

            {visible.length === 0 ? (
              <div className="card">
                <p className="muted">该分类下没有任务。</p>
              </div>
            ) : (
              <>
                {batchGroups.length > 0 && (
                  <section
                    className="production-batches"
                    aria-labelledby="production-batches-title"
                  >
                    <div className="section-heading">
                      <div>
                        <h3 id="production-batches-title">生产批次</h3>
                        <p className="muted">
                          按每次批量生成归组，展开即可查看镜头与处理失败项。
                        </p>
                      </div>
                    </div>
                    <div className="batch-groups">
                      {batchGroups.map((group) => {
                        const completed = group.jobs.filter(
                          (job) => job.status === "completed",
                        ).length;
                        const failed = group.jobs.filter(
                          (job) => job.status === "failed",
                        ).length;
                        const paused = group.jobs.filter(
                          (job) => job.status === "paused",
                        ).length;
                        const interrupted = group.jobs.filter(
                          (job) =>
                            job.status === "paused" &&
                            job.error_category === "interrupted",
                        ).length;
                        const activeJobs = group.jobs.filter((job) =>
                          ["queued", "running", "paused"].includes(job.status),
                        );
                        const processed = group.jobs.filter((job) =>
                          ["completed", "failed", "cancelled"].includes(job.status),
                        ).length;
                        return (
                          <details className="batch-group" key={group.id}>
                            <summary>
                              <div className="batch-group-title">
                                <strong>{group.label}</strong>
                                <span className="muted">
                                  创建于 {formatTime(group.jobs[0].created_at)}
                                </span>
                              </div>
                              <div
                                className="batch-group-summary"
                                aria-label="批次状态汇总"
                              >
                                <span>{completed} 完成</span>
                                {activeJobs.length > interrupted && (
                                  <span className="quality-muted">
                                    {activeJobs.length - interrupted} 进行中
                                  </span>
                                )}
                                {interrupted > 0 && (
                                  <span className="quality-muted">
                                    {interrupted} 待确认恢复
                                  </span>
                                )}
                                {failed > 0 && (
                                  <span className="quality-bad">{failed} 失败</span>
                                )}
                              </div>
                            </summary>
                            <div className="batch-group-body">
                              <div className="batch-progress-line">
                                <progress value={processed} max={group.jobs.length} />
                                <span className="muted">
                                  已处理 {processed} / {group.jobs.length}
                                </span>
                              </div>
                              <div className="batch-group-actions">
                                {activeJobs.some(
                                  (job) =>
                                    job.status === "queued" || job.status === "running",
                                ) && (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      void handleProductionBatch(group.id, "pause")
                                    }
                                  >
                                    暂停批次
                                  </button>
                                )}
                                {paused > interrupted && (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      void handleProductionBatch(group.id, "resume")
                                    }
                                  >
                                    恢复批次
                                  </button>
                                )}
                                {failed > 0 && (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      void handleProductionBatch(group.id, "retry")
                                    }
                                  >
                                    重试失败项
                                  </button>
                                )}
                                {activeJobs.length > 0 && (
                                  <button
                                    type="button"
                                    className={
                                      batchActionArmed[group.id]
                                        ? "button-danger"
                                        : "button-ghost"
                                    }
                                    onClick={() =>
                                      void handleProductionBatch(group.id, "cancel")
                                    }
                                  >
                                    {batchActionArmed[group.id]
                                      ? "确认停止批次"
                                      : "停止批次"}
                                  </button>
                                )}
                              </div>
                              <div className="jobs-list batch-job-list">
                                {group.jobs
                                  .filter((job) => matchesFilter(job, filter))
                                  .map((job) => (
                                    <JobRow
                                      key={job.job_id}
                                      job={job}
                                      cancelArmed={Boolean(cancelArmed[job.job_id])}
                                      resumeArmed={Boolean(resumeArmed[job.job_id])}
                                      onCancel={handleCancel}
                                      onPause={handlePause}
                                      onResume={handleResume}
                                      onRetry={handleRetry}
                                      onJumpToShot={onJumpToShot}
                                    />
                                  ))}
                              </div>
                            </div>
                          </details>
                        );
                      })}
                    </div>
                  </section>
                )}

                {unbatchedVisible.length > 0 && (
                  <section className="other-jobs" aria-labelledby="other-jobs-title">
                    {batchGroups.length > 0 && <h3 id="other-jobs-title">其他任务</h3>}
                    <div className="jobs-list">
                      {unbatchedVisible.map((job) => (
                        <JobRow
                          key={job.job_id}
                          job={job}
                          cancelArmed={Boolean(cancelArmed[job.job_id])}
                          resumeArmed={Boolean(resumeArmed[job.job_id])}
                          onCancel={handleCancel}
                          onPause={handlePause}
                          onResume={handleResume}
                          onRetry={handleRetry}
                          onJumpToShot={onJumpToShot}
                        />
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
