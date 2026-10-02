import { request } from "./client";

export interface PromptStage {
  id: string;
  label: string;
  group: string;
  description: string;
  allow_empty_rules: boolean;
  default_rules: string;
  rules: string;
  default_negative_prompt: string | null;
  negative_prompt: string | null;
  customized: boolean;
  contract: string;
  preview: string;
}

export interface ProjectPromptSettings {
  revision: number;
  stages: PromptStage[];
}

export interface PromptRuleInput {
  rules: string | null;
  negative_prompt?: string | null;
}

export interface PromptRulePreview {
  stage_id: string;
  rules: string;
  negative_prompt: string | null;
  system_prompt: string;
  contract: string;
}

const settingsPath = (projectId: string) =>
  `/projects/${encodeURIComponent(projectId)}/prompt-settings`;

export const getProjectPromptSettings = (projectId: string) =>
  request<ProjectPromptSettings>(settingsPath(projectId));

export const saveProjectPromptStage = (
  projectId: string,
  stageId: string,
  input: PromptRuleInput & { expected_revision: number },
) =>
  request<ProjectPromptSettings>(
    `${settingsPath(projectId)}/${encodeURIComponent(stageId)}`,
    { method: "PUT", body: JSON.stringify(input) },
  );

export const previewProjectPromptStage = (
  projectId: string,
  stageId: string,
  input: PromptRuleInput,
) =>
  request<PromptRulePreview>(
    `${settingsPath(projectId)}/${encodeURIComponent(stageId)}/preview`,
    { method: "POST", body: JSON.stringify(input) },
  );
