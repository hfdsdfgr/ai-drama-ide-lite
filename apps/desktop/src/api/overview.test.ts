import { afterEach, describe, expect, it, vi } from "vitest";

import { getEpisodeWorkspace, prepareEpisode } from "./overview";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(body: unknown) {
  const mock = vi.fn(
    async () => new Response(JSON.stringify(body), { status: 200 }),
  );
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("episode workspace api", () => {
  it("loads the project episode workspace", async () => {
    const mock = stubFetch({ project_id: "proj_1", episodes: [] });
    await getEpisodeWorkspace("proj_1");
    const [url] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(
      "/api/projects/proj_1/overview/episodes",
    );
  });

  it("runs episode preparation as an explicit POST", async () => {
    const mock = stubFetch({
      episode: { episode_id: "ep_1" },
      message: "预检完成",
      created_jobs: 0,
      filled_prompts: 0,
    });
    await prepareEpisode("proj_1", "ep_1");
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/projects/proj_1/overview/episodes/ep_1/prepare");
    expect(init.method).toBe("POST");
  });
});
