import { request } from "./client";

export interface WorkflowConfig {
  auto_continue: boolean;
  storyboard: { enabled: boolean; model_id: string; capability: "llm" };
  shot_images: {
    enabled: boolean;
    model_id: string;
    capability: "text_to_image" | "reference_image" | "image_to_image";
    aspect_ratio: string;
  };
  videos: {
    enabled: boolean;
    model_id: string;
    capability: "image_to_video";
    aspect_ratio: string;
    duration_mode: "shot" | "fixed";
    duration: 5 | 10 | 15;
  };
}

export interface WorkflowTemplate {
  id: string;
  project_id: string;
  name: string;
  description: string;
  schema_version: number;
  revision: number;
  config: WorkflowConfig;
  created_at: string;
  updated_at: string;
}

export interface EpisodeWorkflowConfig {
  project_id: string;
  episode_id: string;
  revision: number;
  config: WorkflowConfig;
  updated_at: string | null;
}

export interface WorkflowDiff {
  field_path: string;
  label: string;
  current_value: string | number | boolean;
  template_value: string | number | boolean;
  compatible: boolean;
  reason: string;
  candidates?: { id: string; name: string }[];
}

export interface WorkflowPreview {
  template_id: string;
  template_revision: number;
  config_revision: number;
  differences: WorkflowDiff[];
}

export const listWorkflowTemplates = (projectId: string) =>
  request<WorkflowTemplate[]>(`/projects/${projectId}/workflow-templates`);

export const createWorkflowTemplate = (
  projectId: string,
  input: { name: string; description?: string; config: WorkflowConfig },
) =>
  request<WorkflowTemplate>(`/projects/${projectId}/workflow-templates`, {
    method: "POST",
    body: JSON.stringify(input),
  });

export const updateWorkflowTemplate = (
  projectId: string,
  templateId: string,
  input: {
    expected_revision: number;
    name?: string;
    description?: string;
    config?: WorkflowConfig;
  },
) =>
  request<WorkflowTemplate>(`/projects/${projectId}/workflow-templates/${templateId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });

export const deleteWorkflowTemplate = (projectId: string, templateId: string) =>
  request<void>(`/projects/${projectId}/workflow-templates/${templateId}`, {
    method: "DELETE",
  });

export const getEpisodeWorkflowConfig = (projectId: string, episodeId: string) =>
  request<EpisodeWorkflowConfig>(
    `/projects/${projectId}/episodes/${episodeId}/workflow-config`,
  );

export const saveEpisodeWorkflowConfig = (
  projectId: string,
  episodeId: string,
  input: { expected_revision: number; config: WorkflowConfig },
) =>
  request<EpisodeWorkflowConfig>(
    `/projects/${projectId}/episodes/${episodeId}/workflow-config`,
    { method: "PUT", body: JSON.stringify(input) },
  );

export const previewWorkflowTemplate = (
  projectId: string,
  episodeId: string,
  templateId: string,
) =>
  request<WorkflowPreview>(
    `/projects/${projectId}/episodes/${episodeId}/workflow-config/preview-template`,
    { method: "POST", body: JSON.stringify({ template_id: templateId }) },
  );

export const applyWorkflowTemplate = (
  projectId: string,
  episodeId: string,
  input: {
    template_id: string;
    template_revision: number;
    config_revision: number;
    selected_fields: string[];
  },
) =>
  request<EpisodeWorkflowConfig>(
    `/projects/${projectId}/episodes/${episodeId}/workflow-config/apply-template`,
    { method: "POST", body: JSON.stringify(input) },
  );
