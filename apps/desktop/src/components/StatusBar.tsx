import { useEffect, useState } from "react";

import { listJobs } from "../api/jobs";
import { listProjects } from "../api/projects";
import { getAppVersion } from "../api/version";
import type { JobOut } from "../types/job";

const ACTIVE_STATUSES: JobOut["status"][] = ["queued", "running", "paused"];

export function StatusBar() {
  const [activeCount, setActiveCount] = useState(0);
  const [progress, setProgress] = useState<number | null>(null);
  const [hasError, setHasError] = useState(false);
  const [appVersion, setAppVersion] = useState("");

  useEffect(() => {
    let cancelled = false;
    let timer: number | null = null;

    async function refresh() {
      try {
        const projects = await listProjects();
        if (cancelled) return;
        const projectId = projects[0]?.id ?? "";
        if (!projectId) {
          setActiveCount(0);
          setProgress(null);
          setHasError(false);
          return;
        }
        const jobs = await listJobs({ project_id: projectId, limit: 200 });
        if (cancelled) return;
        const active = jobs.filter((job) =>
          ACTIVE_STATUSES.includes(job.status),
        );
        const running = active.find(
          (job) => job.status === "running" && job.progress > 0,
        );
        setActiveCount(active.length);
        setProgress(running ? running.progress : null);
        setHasError(false);
      } catch {
        if (!cancelled) setHasError(true);
      }
    }

    void refresh();
    timer = window.setInterval(() => void refresh(), 5000);
    return () => {
      cancelled = true;
      if (timer !== null) window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getAppVersion()
      .then((info) => {
        if (!cancelled) setAppVersion(info.version);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const stateClass = hasError ? "error" : activeCount > 0 ? "active" : "ready";
  const label = hasError
    ? "连接失败"
    : activeCount > 0
      ? `生成中 · ${activeCount} 个任务${progress !== null ? ` · ${progress}%` : ""}`
      : "就绪";

  return (
    <footer className="statusbar">
      <span className="statusbar-item">
        <span className={`status-dot status-dot-${stateClass}`} aria-hidden="true" />
        {label}
      </span>
      <span className="statusbar-spacer" />
      <span className="statusbar-item statusbar-muted">
        AI Drama IDE Lite{appVersion ? ` v${appVersion}` : ""}
      </span>
    </footer>
  );
}
