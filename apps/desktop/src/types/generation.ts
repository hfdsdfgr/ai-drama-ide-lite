export type GenerationStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface GenerationResult {
  urls: string[];
  meta: Record<string, unknown>;
}

export interface GenerationJob {
  job_id: string;
  model_id: string;
  capability: string;
  status: GenerationStatus;
  error: string | null;
  result: GenerationResult | null;
  created_at: string;
}
