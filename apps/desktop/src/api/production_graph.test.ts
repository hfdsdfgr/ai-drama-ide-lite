import { afterEach, describe, expect, it, vi } from "vitest";

import { getAffectedNodes, getRegenerationPlan } from "./production_graph";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("production graph api", () => {
  it("loads downstream affected nodes", async () => {
    const mock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            changed_node: { type: "asset", id: "asset_1" },
            affected: [],
          }),
          { status: 200 },
        ),
    );
    vi.stubGlobal("fetch", mock);

    const result = await getAffectedNodes("proj_1", "asset", "asset_1");

    expect(result.affected).toEqual([]);
    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe(
      "/api/projects/proj_1/graph/affected?node_type=asset&node_id=asset_1",
    );
  });

  it("loads a shot-level regeneration plan", async () => {
    const mock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            changed_node: { type: "asset", id: "asset_1" },
            image_shots: [],
            video_shots: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    );
    vi.stubGlobal("fetch", mock);

    await getRegenerationPlan("proj_1", "asset", "asset_1");

    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe(
      "/api/projects/proj_1/graph/regeneration-plan?node_type=asset&node_id=asset_1",
    );
  });
});
