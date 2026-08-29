import type { JobOut } from "../types/job";
import { request } from "./client";

export interface StoryReview {
  id: string;
  project_id: string;
  shot_id: string;
  mode: "model" | "manual";
  model_id: string;
  status: "pending" | "passed" | "flagged";
  issue: string;
  decision: "" | "regenerate" | "delete_shot" | "keep";
  created_at: string;
  updated_at: string;
}

export function runStoryReview(
  projectId: string,
  input: { shot_id: string; model_id: string },
): Promise<JobOut> {
  return request<JobOut>(
    `/projects/${projectId}/story-reviews/run`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function submitManualStoryReview(
  projectId: string,
  input: { shot_id: string; consistent: boolean; issue?: string },
): Promise<StoryReview> {
  return request<StoryReview>(
    `/projects/${projectId}/story-reviews/manual`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listStoryReviews(
  projectId: string,
  shotId: string,
): Promise<StoryReview[]> {
  return request<StoryReview[]>(
    `/projects/${projectId}/story-reviews?shot_id=${shotId}`,
  );
}

export function decideStoryReview(
  projectId: string,
  reviewId: string,
  decision: "regenerate" | "delete_shot" | "keep",
): Promise<StoryReview> {
  return request<StoryReview>(
    `/projects/${projectId}/story-reviews/${reviewId}/decision`,
    { method: "POST", body: JSON.stringify({ decision }) },
  );
}
