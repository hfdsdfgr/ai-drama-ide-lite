import type { JobOut } from "../types/job";
import { request } from "./client";

export interface DialogueReview {
  id: string;
  project_id: string;
  shot_id: string;
  video_version_id: string;
  mode: "model" | "manual";
  model_id: string;
  status: "pending" | "passed" | "flagged";
  detected_speech: string;
  expected_dialogue: string;
  issue: string;
  decision: "" | "regenerate" | "delete_shot" | "keep";
  created_at: string;
  updated_at: string;
}

export function runDialogueReview(
  projectId: string,
  input: { shot_id: string; model_id: string; script_model_id: string },
): Promise<JobOut> {
  return request<JobOut>(
    `/projects/${projectId}/dialogue-reviews/run`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function submitManualReview(
  projectId: string,
  input: { shot_id: string; consistent: boolean; detected_speech?: string },
): Promise<DialogueReview> {
  return request<DialogueReview>(
    `/projects/${projectId}/dialogue-reviews/manual`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listDialogueReviews(
  projectId: string,
  shotId: string,
): Promise<DialogueReview[]> {
  return request<DialogueReview[]>(
    `/projects/${projectId}/dialogue-reviews?shot_id=${shotId}`,
  );
}

export function decideDialogueReview(
  projectId: string,
  reviewId: string,
  decision: "regenerate" | "delete_shot" | "keep",
): Promise<DialogueReview> {
  return request<DialogueReview>(
    `/projects/${projectId}/dialogue-reviews/${reviewId}/decision`,
    { method: "POST", body: JSON.stringify({ decision }) },
  );
}
