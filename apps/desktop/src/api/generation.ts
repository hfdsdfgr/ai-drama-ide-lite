import type { GenerationJob } from "../types/generation";
import { request } from "./client";

export function createGenerationJob(input: {
  model_id: string;
  capability: string;
  prompt: string;
}): Promise<GenerationJob> {
  return request<GenerationJob>("/generation/jobs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getGenerationJob(jobId: string): Promise<GenerationJob> {
  return request<GenerationJob>(`/generation/jobs/${jobId}`);
}
