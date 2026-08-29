import type { JobOut } from "../types/job";
import { request } from "./client";

export type VisualReviewType =
  | "character"
  | "scene"
  | "continuity"
  | "costume";

export interface VisualReview {
  id: string;
  project_id: string;
  shot_id: string;
  image_version_id: string;
  review_type: VisualReviewType;
  mode: "model" | "manual";
  model_id: string;
  status: "pending" | "passed" | "flagged";
  issue: string;
  decision: "" | "regenerate" | "delete_shot" | "keep";
  created_at: string;
  updated_at: string;
}

export function runVisualReview(
  projectId: string,
  input: { shot_id: string; model_id: string; review_type: VisualReviewType },
): Promise<JobOut> {
  return request<JobOut>(
    `/projects/${projectId}/visual-reviews/run`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function submitManualVisualReview(
  projectId: string,
  input: {
    shot_id: string;
    review_type: VisualReviewType;
    consistent: boolean;
    issue?: string;
  },
): Promise<VisualReview> {
  return request<VisualReview>(
    `/projects/${projectId}/visual-reviews/manual`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listVisualReviews(
  projectId: string,
  shotId: string,
): Promise<VisualReview[]> {
  return request<VisualReview[]>(
    `/projects/${projectId}/visual-reviews?shot_id=${shotId}`,
  );
}

export function decideVisualReview(
  projectId: string,
  reviewId: string,
  decision: "regenerate" | "delete_shot" | "keep",
): Promise<VisualReview> {
  return request<VisualReview>(
    `/projects/${projectId}/visual-reviews/${reviewId}/decision`,
    { method: "POST", body: JSON.stringify({ decision }) },
  );
}
