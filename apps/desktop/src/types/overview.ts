export type StageStatus = "pending" | "active" | "completed";

export interface StageOut {
  key: string;
  label: string;
  status: StageStatus;
  detail: string;
}

export interface ProjectOverview {
  project_id: string;
  stages: StageOut[];
}
