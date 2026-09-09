import { afterEach, describe, expect, it, vi } from "vitest";

import { createBatchImages, planBatchImages } from "./images";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("batch image api", () => {
  it("plans and creates independent image jobs", async () => {
    const mock = vi.fn(
      async () =>
        new Response(JSON.stringify({ ready: [], skipped: [], jobs: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", mock);

    await planBatchImages("proj_1", { model_id: "model_1", shot_ids: ["shot_1"] });
    await createBatchImages("proj_1", {
      model_id: "model_1",
      shot_ids: ["shot_1"],
      batch_label: "第 1 集",
    });

    const [planUrl] = mock.mock.calls[0] as unknown as [string];
    const [createUrl] = mock.mock.calls[1] as unknown as [string];
    expect(planUrl).toBe("/api/projects/proj_1/images/batch-plan");
    expect(createUrl).toBe("/api/projects/proj_1/images/batch-generate");
  });
});
