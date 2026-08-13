import type { AnalysisJob, AnalysisMode, StoryBible } from "../types/story";
import { request } from "./client";

export function startStoryAnalysis(
  projectId: string,
  novelId: string,
  modelId: string,
  mode: AnalysisMode,
): Promise<AnalysisJob> {
  return request<AnalysisJob>(`/projects/${projectId}/story/analysis`, {
    method: "POST",
    body: JSON.stringify({
      novel_id: novelId,
      model_id: modelId,
      mode,
    }),
  });
}

export function getStoryAnalysis(
  projectId: string,
  jobId: string,
): Promise<AnalysisJob> {
  return request<AnalysisJob>(
    `/projects/${projectId}/story/analysis/${jobId}`,
  );
}

export function getStoryBible(
  projectId: string,
): Promise<{ bible: StoryBible | null }> {
  return request<{ bible: StoryBible | null }>(
    `/projects/${projectId}/story/bible`,
  );
}
