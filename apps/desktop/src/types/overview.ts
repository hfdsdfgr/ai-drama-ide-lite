export type StageStatus = "pending" | "active" | "completed";

export interface StageJob {
  job_id: string;
  capability: string;
  status: string;
  progress: number;
  target_label: string;
}

export interface StageOut {
  key: string;
  label: string;
  status: StageStatus;
  detail: string;
  jobs: StageJob[];
}

export interface ProjectOverview {
  project_id: string;
  stages: StageOut[];
}
