import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createProvider,
  getGenerationParameterSchema,
  listModels,
  recommendModels,
  testProvider,
  updateModelCapabilities,
  validateGenerationParameters,
} from "./providers";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(responseBody: unknown, status = 200) {
  const mock = vi.fn(async () => new Response(JSON.stringify(responseBody), { status }));
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("providers api", () => {
  it("createProvider posts preset and api key", async () => {
    const mock = stubFetch({ id: "prov_1" }, 201);
    await createProvider({ preset_key: "openai", api_key: "sk-1" });
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/providers");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      preset_key: "openai",
      api_key: "sk-1",
    });
  });

  it("listModels appends query params", async () => {
    const mock = stubFetch([]);
    await listModels({
      model_type: "image",
      enabled_only: true,
      capability: "image_to_video",
    });
    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe(
      "/api/models?model_type=image&enabled_only=true&capability=image_to_video",
    );
  });

  it("recommendModels posts capability and preference", async () => {
    const mock = stubFetch({ recommended: null, alternatives: [] });
    await recommendModels({
      model_type: "video",
      required_capabilities: ["image_to_video"],
      preference: "quality",
    });
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/models/recommendation");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      model_type: "video",
      required_capabilities: ["image_to_video"],
      preference: "quality",
    });
  });

  it("testProvider posts to provider test endpoint", async () => {
    const mock = stubFetch({ provider_id: "prov_1", ok: true, checks: [] });
    await testProvider("prov_1");
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/providers/prov_1/test");
    expect(init.method).toBe("POST");
  });

  it("updateModelCapabilities puts manual capabilities", async () => {
    const mock = stubFetch({ id: "model_1", capabilities: ["text_to_image"] });
    await updateModelCapabilities("model_1", ["text_to_image"], "manual");
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/models/model_1/capabilities");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({
      capabilities: ["text_to_image"],
      source: "manual",
    });
  });

  it("gets the parameter schema for one model capability", async () => {
    const mock = stubFetch({ model_id: "model_1", fields: [] });
    await getGenerationParameterSchema("model_1", "image_to_video");
    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe("/api/models/model_1/generation-schema?capability=image_to_video");
  });

  it("validates parameter values before generation", async () => {
    const mock = stubFetch({
      model_id: "model_1",
      capability: "image_to_video",
      values: { duration: 10 },
    });
    await validateGenerationParameters("model_1", "image_to_video", {
      duration: 10,
    });
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/models/model_1/generation-schema/validate");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      capability: "image_to_video",
      values: { duration: 10 },
    });
  });
});
