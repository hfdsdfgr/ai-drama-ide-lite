export type ModelType = "llm" | "image" | "video";

export interface Preset {
  key: string;
  name: string;
  base_url: string;
  needs_key: boolean;
  discoverable: boolean;
}

export interface Provider {
  id: string;
  name: string;
  preset_key: string | null;
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
  api_base_url?: string;
  needs_key?: boolean;
  api_key?: string;
  enabled?: boolean;
}

export interface Model {
  id: string;
  provider_id: string;
  provider_name: string;
  provider_base_url: string;
  provider_needs_key: boolean;
  provider_has_api_key: boolean;
  model_id: string;
  model_type: ModelType;
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
