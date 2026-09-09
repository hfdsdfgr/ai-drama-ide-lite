export type JobStatus =
  "queued" | "running" | "paused" | "completed" | "failed" | "cancelled";

export interface JobOut {
  job_id: string;
  project_id: string | null;
  type: string;
  status: JobStatus;
  progress: number;
  model_id: string;
  provider_id: string;
  capability: string;
  error: string | null;
  error_category: string;
  attempts: number;
  result: Record<string, unknown> | null;
  batch_id: string;
  batch_label: string;
  target_id: string;
  target_label: string;
  has_remote_task: boolean;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  paused_at: string | null;
  cancelled_at: string | null;
}

export interface ProjectJobState {
  project_id: string;
  paused: boolean;
}
