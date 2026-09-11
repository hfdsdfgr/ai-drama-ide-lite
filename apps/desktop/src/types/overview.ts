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

export type ProductionState =
  | "missing"
  | "ready"
  | "stale"
  | "active"
  | "failed"
  | "pending"
  | "passed"
  | "flagged"
  | "not_started"
  | "not_referenced";

export interface EpisodeAsset {
  asset_id: string;
  asset_type: "character" | "location" | "prop";
  name: string;
  has_image: boolean;
}

export interface EpisodeBlocker {
  code: string;
  label: string;
  target: "assets" | "storyboard";
}

export interface EpisodeShot {
  shot_id: string;
  scene_id: string;
  scene_title: string;
  shot_number: number | null;
  order_index: number;
  script_status: ProductionState;
  asset_status: ProductionState;
  prompt_status: ProductionState;
  image_status: ProductionState;
  video_status: ProductionState;
  review_status: ProductionState;
  assets: EpisodeAsset[];
  blockers: EpisodeBlocker[];
  image_dependency_state?: DependencyState;
  video_dependency_state?: DependencyState;
  dependency_issues?: DependencyIssue[];
}

export type DependencyState =
  "none" | "current" | "stale" | "pinned" | "unknown" | "broken";
export interface DependencyIssue {
  state: DependencyState;
  label: string;
  media: "image" | "video";
  source_id: string;
  source_name: string;
  used_version_id: string;
  used_version: number | null;
  current_version_id: string;
  current_version: number | null;
}

export interface EpisodeProduction {
  episode_id: string;
  title: string;
  order_index: number;
  scene_count: number;
  shot_count: number;
  completed_shots: number;
  attention_count: number;
  active_count: number;
  stale_count?: number;
  unknown_dependency_count?: number;
  pinned_dependency_count?: number;
  shots: EpisodeShot[];
}

export interface EpisodeWorkspace {
  project_id: string;
  episodes: EpisodeProduction[];
}

export interface EpisodePrepareResult {
  episode: EpisodeProduction;
  message: string;
  created_jobs: number;
  filled_prompts: number;
}
