import type { JobOut, JobStatus, ProjectJobState } from "../types/job";
import { request } from "./client";

export function listJobs(params?: {
  project_id?: string;
  status?: JobStatus;
  limit?: number;
}): Promise<JobOut[]> {
  const query = new URLSearchParams();
  if (params?.project_id) query.set("project_id", params.project_id);
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return request<JobOut[]>(`/jobs${qs ? `?${qs}` : ""}`);
}

export function getJob(jobId: string): Promise<JobOut> {
  return request<JobOut>(`/jobs/${jobId}`);
}

export function getProjectJobState(projectId: string): Promise<ProjectJobState> {
  return request<ProjectJobState>(
    `/jobs/project-state?project_id=${encodeURIComponent(projectId)}`,
  );
}

export function cancelJob(jobId: string): Promise<JobOut> {
  return request<JobOut>(`/jobs/${jobId}/cancel`, { method: "POST" });
}

export function pauseJob(jobId: string): Promise<JobOut> {
  return request<JobOut>(`/jobs/${jobId}/pause`, { method: "POST" });
}

export function resumeJob(jobId: string): Promise<JobOut> {
  return request<JobOut>(`/jobs/${jobId}/resume`, { method: "POST" });
}

export function retryJob(jobId: string): Promise<JobOut> {
  return request<JobOut>(`/jobs/${jobId}/retry`, { method: "POST" });
}

export interface BatchJobsResult {
  affected: number;
  jobs: JobOut[];
  project_paused: boolean;
}

export function batchJobs(params: {
  project_id: string;
  action: "cancel" | "pause" | "resume" | "retry";
  stage?: string;
  batch_id?: string;
}): Promise<BatchJobsResult> {
  return request<BatchJobsResult>(`/jobs/batch`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}
