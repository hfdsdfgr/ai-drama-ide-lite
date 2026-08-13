import { afterEach, describe, expect, it, vi } from "vitest";

import { createProvider, listModels } from "./providers";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(responseBody: unknown, status = 200) {
  const mock = vi.fn(
    async () =>
      new Response(JSON.stringify(responseBody), { status }),
  );
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
    await listModels({ model_type: "image", enabled_only: true });
    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe("/api/models?model_type=image&enabled_only=true");
  });
});
