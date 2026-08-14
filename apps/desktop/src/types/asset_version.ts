export interface AssetVersion {
  id: string;
  entity_type: string;
  entity_id: string;
  version: number;
  model_id: string;
  provider_id: string;
  job_id: string;
  payload: Record<string, unknown>;
  is_current: boolean;
  created_at: string;
  file_url: string;
}
