import type { AssetVersion } from "../types/asset_version";
import type { GenerationJob } from "../types/generation";
import { request } from "./client";

export interface ImageGenerateInput {
  target_type: "asset" | "shot";
  target_id: string;
  model_id: string;
  capability?: string;
  aspect_ratio?: string;
  art_style?: string;
  negative_prompt?: string;
  reference_asset_ids?: string[];
  reference_version_ids?: string[];
  pinned_version_ids?: string[];
  prompt?: string;
  regenerated_from_version_id?: string;
}

export interface BatchImagePlanItem {
  shot_id: string;
  label: string;
  reason: string;
}

export interface BatchImagePlan {
  ready: BatchImagePlanItem[];
  skipped: BatchImagePlanItem[];
}

export interface BatchImageResult extends BatchImagePlan {
  batch_id: string;
  jobs: GenerationJob[];
}

export function generateImage(
  projectId: string,
  input: ImageGenerateInput,
): Promise<GenerationJob> {
  return request<GenerationJob>(`/projects/${projectId}/images/generate`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getImageJob(projectId: string, jobId: string): Promise<GenerationJob> {
  return request<GenerationJob>(`/projects/${projectId}/images/jobs/${jobId}`);
}

export function planBatchImages(
  projectId: string,
  input: { model_id: string; shot_ids: string[] },
): Promise<BatchImagePlan> {
  return request<BatchImagePlan>(`/projects/${projectId}/images/batch-plan`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createBatchImages(
  projectId: string,
  input: { model_id: string; shot_ids: string[]; batch_label: string },
): Promise<BatchImageResult> {
  return request<BatchImageResult>(`/projects/${projectId}/images/batch-generate`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function importShotImage(
  projectId: string,
  shotId: string,
  file: File,
): Promise<AssetVersion> {
  const form = new FormData();
  form.append("file", file);
  return request<AssetVersion>(`/projects/${projectId}/images/shots/${shotId}/import`, {
    method: "POST",
    headers: {},
    body: form,
  });
}

export function listImageVersions(
  projectId: string,
  targetType: "asset" | "shot",
  targetId: string,
): Promise<AssetVersion[]> {
  return request<AssetVersion[]>(
    `/projects/${projectId}/images/versions?target_type=${targetType}&target_id=${targetId}`,
  );
}

export function getCurrentImageVersion(
  projectId: string,
  targetType: "asset" | "shot",
  targetId: string,
): Promise<AssetVersion | null> {
  return request<AssetVersion | null>(
    `/projects/${projectId}/images/current?target_type=${targetType}&target_id=${targetId}`,
  );
}
