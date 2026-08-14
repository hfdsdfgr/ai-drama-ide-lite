import { afterEach, describe, expect, it, vi } from "vitest";

import {
  deleteAssetVersion,
  listAssetVersions,
  promoteAssetVersion,
} from "./asset_versions";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(responseBody: unknown, status = 200) {
  const mock = vi.fn(
    async () => new Response(JSON.stringify(responseBody), { status }),
  );
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("asset versions api", () => {
  it("listAssetVersions fetches version list", async () => {
    const mock = stubFetch([{ id: "ver_1", version: 1 }]);
    const versions = await listAssetVersions("proj_1", "asset_1");
    expect(versions).toEqual([{ id: "ver_1", version: 1 }]);
    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe("/api/projects/proj_1/assets/asset_1/versions");
  });

  it("promoteAssetVersion posts to promote endpoint", async () => {
    const mock = stubFetch({ id: "ver_1", is_current: true });
    await promoteAssetVersion("proj_1", "asset_1", "ver_1");
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(
      "/api/projects/proj_1/assets/asset_1/versions/ver_1/promote",
    );
    expect(init.method).toBe("POST");
  });

  it("deleteAssetVersion deletes version", async () => {
    const mock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", mock);
    await deleteAssetVersion("proj_1", "asset_1", "ver_1");
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(
      "/api/projects/proj_1/assets/asset_1/versions/ver_1",
    );
    expect(init.method).toBe("DELETE");
  });
});
