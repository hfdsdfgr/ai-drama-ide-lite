import { request } from "./client";

export interface QualityReview {
  id: string;
  shot_id: string;
  review_type?: string;
  mode: string;
  status: "pending" | "passed" | "flagged";
  issue: string;
  decision: string;
  created_at: string;
}

export interface QualityItem {
  shot_id: string;
  shot_number: number | null;
  order_index: number;
  scene_title: string;
  has_image: boolean;
  status: "pending" | "passed" | "flagged";
  reviews: QualityReview[];
}

export interface ProjectQuality {
  project_id: string;
  summary: {
    flagged: number;
    passed: number;
    pending: number;
    total: number;
  };
  items: QualityItem[];
}

export function getProjectQuality(projectId: string): Promise<ProjectQuality> {
  return request<ProjectQuality>(`/projects/${projectId}/quality`);
}
