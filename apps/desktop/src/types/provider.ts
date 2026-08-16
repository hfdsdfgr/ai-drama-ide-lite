export type ModelType = "llm" | "image" | "video";
export type ProviderProtocol =
  | "openai_compat"
  | "dashscope"
  | "sora"
  | "openrouter_video"
  | "zhipu_video"
  | "siliconflow_video";

export const PROTOCOL_LABELS: Record<ProviderProtocol, string> = {
  openai_compat: "OpenAI 兼容",
  dashscope: "阿里云百炼 / DashScope",
  sora: "OpenAI Sora",
  openrouter_video: "OpenRouter Video",
  zhipu_video: "智谱 CogVideoX",
  siliconflow_video: "SiliconFlow Video",
};

export type CapabilityKey =
  | "text_to_image"
  | "image_to_image"
  | "reference_image"
  | "character_reference"
  | "text_to_video"
  | "image_to_video"
  | "video_to_video"
  | "first_frame"
  | "last_frame"
  | "first_last_frame";

export const CAPABILITY_LABELS: Record<CapabilityKey, string> = {
  text_to_image: "文生图",
  image_to_image: "图生图",
  reference_image: "参考图",
  character_reference: "角色参考",
  text_to_video: "文生视频",
  image_to_video: "图生视频",
  video_to_video: "视频生视频",
  first_frame: "首帧控制",
  last_frame: "尾帧控制",
  first_last_frame: "首尾帧控制",
};

export const IMAGE_CAPABILITIES: CapabilityKey[] = [
  "text_to_image",
  "image_to_image",
  "reference_image",
  "character_reference",
];

export const VIDEO_CAPABILITIES: CapabilityKey[] = [
  "text_to_video",
  "image_to_video",
  "video_to_video",
  "first_frame",
  "last_frame",
  "first_last_frame",
];

export interface Preset {
  key: string;
  name: string;
  base_url: string;
  needs_key: boolean;
  protocol: ProviderProtocol;
  discoverable: boolean;
}

export interface Provider {
  id: string;
  name: string;
  preset_key: string | null;
  protocol: ProviderProtocol;
  api_base_url: string;
  needs_key: boolean;
  enabled: boolean;
  has_api_key: boolean;
  model_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProviderInput {
  name?: string;
  preset_key?: string;
  protocol?: ProviderProtocol;
  api_base_url?: string;
  needs_key?: boolean;
  api_key?: string;
  enabled?: boolean;
}

export interface Model {
  id: string;
  provider_id: string;
  provider_name: string;
  provider_preset_key?: string | null;
  provider_protocol?: ProviderProtocol;
  provider_base_url: string;
  provider_needs_key: boolean;
  provider_has_api_key: boolean;
  model_id: string;
  model_type: ModelType;
  capabilities: CapabilityKey[];
  capability_source: "auto" | "manual";
  enabled: boolean;
  is_default_image: boolean;
  is_default_video: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelInput {
  provider_id: string;
  model_id: string;
  model_type: ModelType;
  enabled?: boolean;
}

export interface BuiltinModel {
  id: string;
  type: ModelType;
  capabilities: CapabilityKey[];
}

export interface ProviderCheck {
  label: string;
  status: "ok" | "fail" | "skipped";
  detail: string;
}

export interface ModelCheck {
  model_id: string;
  ok: boolean;
  detail: string;
}

export interface ProviderTestResult {
  provider_id: string;
  ok: boolean;
  checks: ProviderCheck[];
  model_checks: ModelCheck[];
  tested_at: string;
}
