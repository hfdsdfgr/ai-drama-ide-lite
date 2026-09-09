import { afterEach, describe, expect, it, vi } from "vitest";

import { batchJobs, cancelJob, getProjectJobState, listJobs, retryJob } from "./jobs";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(responseBody: unknown, status = 200) {
  const mock = vi.fn(async () => new Response(JSON.stringify(responseBody), { status }));
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("jobs api", () => {
  it("listJobs fetches all jobs", async () => {
    const mock = stubFetch([{ job_id: "job_1" }]);
    const jobs = await listJobs();
    expect(jobs).toEqual([{ job_id: "job_1" }]);
    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe("/api/jobs");
  });

  it("listJobs passes query params", async () => {
    const mock = stubFetch([]);
    await listJobs({ project_id: "proj_1", status: "running", limit: 20 });
    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe("/api/jobs?project_id=proj_1&status=running&limit=20");
  });

  it("cancelJob posts to cancel endpoint", async () => {
    const mock = stubFetch({ job_id: "job_1", status: "cancelled" });
    const job = await cancelJob("job_1");
    expect(job.status).toBe("cancelled");
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/jobs/job_1/cancel");
    expect(init.method).toBe("POST");
  });

  it("reads the persistent project pause state", async () => {
    const mock = stubFetch({ project_id: "proj_1", paused: true });
    const state = await getProjectJobState("proj_1");
    expect(state.paused).toBe(true);
    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe("/api/jobs/project-state?project_id=proj_1");
  });

  it("retryJob posts to retry endpoint", async () => {
    const mock = stubFetch({ job_id: "job_1", status: "queued" });
    await retryJob("job_1");
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/jobs/job_1/retry");
    expect(init.method).toBe("POST");
  });

  it("scopes a batch action to one production batch", async () => {
    const mock = stubFetch({ affected: 2, jobs: [] });
    await batchJobs({
      project_id: "proj_1",
      batch_id: "batch_1",
      action: "retry",
    });

    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/jobs/batch");
    expect(JSON.parse(String(init.body))).toEqual({
      project_id: "proj_1",
      batch_id: "batch_1",
      action: "retry",
    });
  });
});
