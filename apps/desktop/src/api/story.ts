import type {
  AiChapter,
  AiNovelBrief,
  AiOutlineResult,
  AnalysisJob,
  AnalysisMode,
  OutlineChapter,
  StoryBible,
} from "../types/story";
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

export function generateAiOutline(
  projectId: string,
  modelId: string,
  brief: AiNovelBrief,
): Promise<AiOutlineResult> {
  return request<AiOutlineResult>(`/projects/${projectId}/story/ai-outline`, {
    method: "POST",
    body: JSON.stringify({ model_id: modelId, brief }),
  });
}

export function generateAiChapter(
  projectId: string,
  input: {
    model_id: string;
    brief: AiNovelBrief;
    outline: OutlineChapter[];
    chapter_index: number;
    user_instruction: string;
    previous_summaries: string[];
  },
): Promise<AiChapter> {
  return request<AiChapter>(`/projects/${projectId}/story/ai-chapter`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}
