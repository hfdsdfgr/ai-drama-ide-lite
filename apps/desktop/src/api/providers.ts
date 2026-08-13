import type {
  BuiltinModel,
  CapabilityKey,
  Model,
  ModelInput,
  ModelType,
  Preset,
  Provider,
  ProviderInput,
  ProviderTestResult,
} from "../types/provider";
import { request } from "./client";

export function listPresets(): Promise<Preset[]> {
  return request<Preset[]>("/providers/presets");
}

export function listProviders(): Promise<Provider[]> {
  return request<Provider[]>("/providers");
}

export function createProvider(input: ProviderInput): Promise<Provider> {
  return request<Provider>("/providers", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateProvider(
  id: string,
  input: ProviderInput,
): Promise<Provider> {
  return request<Provider>(`/providers/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function deleteProvider(id: string): Promise<void> {
  return request<void>(`/providers/${id}`, { method: "DELETE" });
}

export function discoverModels(providerId: string): Promise<Model[]> {
  return request<Model[]>(`/providers/${providerId}/discover-models`, {
    method: "POST",
  });
}

export function testProvider(providerId: string): Promise<ProviderTestResult> {
  return request<ProviderTestResult>(`/providers/${providerId}/test`, {
    method: "POST",
  });
}

export function getPresetModels(presetKey: string): Promise<BuiltinModel[]> {
  return request<BuiltinModel[]>(`/providers/presets/${presetKey}/models`);
}

export function bulkAddModels(
  providerId: string,
  modelIds: string[],
): Promise<Model[]> {
  return request<Model[]>(`/providers/${providerId}/models/bulk`, {
    method: "POST",
    body: JSON.stringify({ model_ids: modelIds }),
  });
}

export function listModels(params?: {
  provider_id?: string;
  model_type?: ModelType;
  enabled_only?: boolean;
  capability?: CapabilityKey;
}): Promise<Model[]> {
  const query = new URLSearchParams();
  if (params?.provider_id) query.set("provider_id", params.provider_id);
  if (params?.model_type) query.set("model_type", params.model_type);
  if (params?.enabled_only) query.set("enabled_only", "true");
  if (params?.capability) query.set("capability", params.capability);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<Model[]>(`/models${suffix}`);
}

export function createModel(input: ModelInput): Promise<Model> {
  return request<Model>("/models", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateModel(
  id: string,
  input: { model_type?: ModelType; enabled?: boolean },
): Promise<Model> {
  return request<Model>(`/models/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function updateModelCapabilities(
  id: string,
  capabilities: CapabilityKey[],
  source: "auto" | "manual" = "manual",
): Promise<Model> {
  return request<Model>(`/models/${id}/capabilities`, {
    method: "PUT",
    body: JSON.stringify({ capabilities, source }),
  });
}

export function deleteModel(id: string): Promise<void> {
  return request<void>(`/models/${id}`, { method: "DELETE" });
}

export function setDefaultModel(
  id: string,
  modelType: "image" | "video",
): Promise<Model> {
  return request<Model>(`/models/${id}/default`, {
    method: "POST",
    body: JSON.stringify({ model_type: modelType }),
  });
}
