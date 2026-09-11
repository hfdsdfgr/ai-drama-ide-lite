import type { JobOut } from "../types/job";
import type { WorkflowConfig } from "./workflowTemplates";
import { request } from "./client";

export interface PipelineStagePlan {
  key: string;
  label: string;
  kind: "llm" | "image" | "video" | "review";
  status: "ready" | "not_ready" | "completed" | "disabled";
  model_id: string;
  missing_reason: string;
}

export interface EpisodePipelinePlan extends PipelinePlan {
  episode_id: string;
  episode_title: string;
  config_revision: number;
  config: WorkflowConfig;
}

export interface PipelinePlan {
  project_id: string;
  stages: PipelineStagePlan[];
  can_start: boolean;
}

export interface PipelineStageStatus {
  project_id: string;
  stage_key: string;
  status: string;
  message: string;
  updated_at: string;
}

export interface PipelineStatus {
  project_id: string;
  stages: PipelineStageStatus[];
}

export function getPipelinePlan(projectId: string): Promise<PipelinePlan> {
  return request<PipelinePlan>(`/projects/${projectId}/pipeline/plan`);
}

export function startPipeline(
  projectId: string,
  input: {
    auto_continue?: boolean;
    include_videos?: boolean;
    quality_review?: boolean;
  },
): Promise<JobOut> {
  return request<JobOut>(`/projects/${projectId}/pipeline/start`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getPipelineStatus(projectId: string): Promise<PipelineStatus> {
  return request<PipelineStatus>(`/projects/${projectId}/pipeline/status`);
}

export function getEpisodePipelinePlan(
  projectId: string,
  episodeId: string,
): Promise<EpisodePipelinePlan> {
  return request<EpisodePipelinePlan>(
    `/projects/${projectId}/pipeline/episodes/${episodeId}/plan`,
  );
}

export function startEpisodePipeline(
  projectId: string,
  episodeId: string,
  expectedConfigRevision: number,
): Promise<JobOut> {
  return request<JobOut>(
    `/projects/${projectId}/pipeline/episodes/${episodeId}/start`,
    {
      method: "POST",
      body: JSON.stringify({ expected_config_revision: expectedConfigRevision }),
    },
  );
}

export function getEpisodePipelineStatus(
  projectId: string,
  episodeId: string,
  jobId: string,
): Promise<PipelineStatus> {
  return request<PipelineStatus>(
    `/projects/${projectId}/pipeline/episodes/${episodeId}/status?job_id=${encodeURIComponent(jobId)}`,
  );
}
