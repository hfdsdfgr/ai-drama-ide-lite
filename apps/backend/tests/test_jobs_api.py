"""Phase 10 — 统一任务中心接口测试（/api/jobs）。"""

from app.db.database import get_connection
from app.services.job_store import (
    CATEGORY_INTERRUPTED,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PAUSED,
    STATUS_QUEUED,
    STATUS_RUNNING,
)


def _make_job(client, **kwargs):
    return client.app.state.job_store.create(
        "generation",
        None,
        model_id="model_x",
        provider_id="prov_1",
        capability="text_to_image",
        input_payload={"prompt": "x"},
        **kwargs,
    )


def test_list_jobs_empty(client):
    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert response.json() == []


def test_list_and_get_job(client):
    job = _make_job(client)

    listed = client.get("/api/jobs").json()
    assert [j["job_id"] for j in listed] == [job.id]
    assert listed[0]["status"] == STATUS_QUEUED
    assert listed[0]["type"] == "generation"
    assert listed[0]["model_id"] == "model_x"
    assert listed[0]["provider_id"] == "prov_1"
    assert listed[0]["capability"] == "text_to_image"
    assert listed[0]["batch_id"] == ""
    assert listed[0]["has_remote_task"] is False

    detail = client.get(f"/api/jobs/{job.id}").json()
    assert detail["job_id"] == job.id
    assert detail["status"] == STATUS_QUEUED


def test_cancel_job(client):
    job = _make_job(client)
    response = client.post(f"/api/jobs/{job.id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == STATUS_CANCELLED
    assert response.json()["cancelled_at"]  # 透传字段存在


def test_pause_resume_job(client):
    store = client.app.state.job_store
    job = _make_job(client)
    # 非 running 不能暂停
    assert client.post(f"/api/jobs/{job.id}/pause").json()["status"] == STATUS_QUEUED
    store.mark_running(job.id)
    assert (
        client.post(f"/api/jobs/{job.id}/pause").json()["status"] == STATUS_PAUSED
    )
    assert client.post(f"/api/jobs/{job.id}/resume").json()["status"] == STATUS_QUEUED


def test_retry_failed_job(client):
    store = client.app.state.job_store
    job = _make_job(client)
    store.mark_running(job.id)
    store.mark_failed(job.id, "boom", "retryable")

    failed = client.get(f"/api/jobs/{job.id}").json()
    assert failed["status"] == STATUS_FAILED
    assert failed["error"] == "boom"
    assert failed["error_category"] == "retryable"

    response = client.post(f"/api/jobs/{job.id}/retry")
    assert response.status_code == 200
    retried = response.json()
    assert retried["status"] == STATUS_QUEUED
    assert retried["error"] is None
    assert retried["attempts"] == 0


def test_job_not_found(client):
    response = client.get("/api/jobs/job_none")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


def test_invalid_limit(client):
    response = client.get("/api/jobs", params={"limit": 999})
    assert response.status_code == 422


def test_completed_job_exposes_result(client):
    store = client.app.state.job_store
    job = _make_job(client)
    store.mark_running(job.id)
    store.mark_completed(job.id, result_payload={"urls": ["https://cdn/x.png"]})

    detail = client.get(f"/api/jobs/{job.id}").json()
    assert detail["status"] == STATUS_COMPLETED
    assert detail["progress"] == 100
    assert detail["result"] == {"urls": ["https://cdn/x.png"]}


def _make_project_job(client, project_id: str, **kwargs):
    return client.app.state.job_store.create(
        "generation",
        project_id,
        model_id="model_x",
        provider_id="prov_1",
        capability="text_to_image",
        input_payload={},
        **kwargs,
    )


def test_batch_cancel_project_preserves_completed(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    store = client.app.state.job_store
    queued = _make_project_job(client, project_id)
    running = _make_project_job(client, project_id)
    store.mark_running(running.id)
    done = _make_project_job(client, project_id)
    store.mark_running(done.id)
    store.mark_completed(done.id)

    response = client.post(
        "/api/jobs/batch",
        json={"project_id": project_id, "action": "cancel"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["affected"] == 2
    statuses = {job["job_id"]: job["status"] for job in body["jobs"]}
    assert statuses[queued.id] == STATUS_CANCELLED
    assert statuses[running.id] == STATUS_CANCELLED
    assert all(job["job_id"] != done.id for job in body["jobs"])
    assert store.get(done.id).status == STATUS_COMPLETED


def test_batch_cancel_stage_only(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    store = client.app.state.job_store
    db_path = client.app.state.settings.db_path
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('sc1', ?, NULL, NULL, '', 0, '', '', '', NULL, ?, ?)",
            (project_id, now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', ?, 'sc1', 1, 0, '', '', '', '', '', '', 5, '', NULL, ?, ?)",
            (project_id, now, now),
        )
    video_job = store.create(
        "generation",
        project_id,
        model_id="m",
        provider_id="p",
        capability="image_to_video",
        input_payload={
            "extra": {"target_type": "shot", "target_id": "shot1"}
        },
    )
    store.mark_running(video_job.id)
    image_job = _make_project_job(client, project_id)
    store.mark_running(image_job.id)

    response = client.post(
        "/api/jobs/batch",
        json={
            "project_id": project_id,
            "action": "cancel",
            "stage": "video_generation",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["affected"] == 1
    assert body["jobs"][0]["job_id"] == video_job.id
    assert body["jobs"][0]["status"] == STATUS_CANCELLED
    assert store.get(image_job.id).status == STATUS_RUNNING


def test_batch_pause_and_resume(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    store = client.app.state.job_store
    running = _make_project_job(client, project_id)
    store.mark_running(running.id)
    queued = _make_project_job(client, project_id)

    paused = client.post(
        "/api/jobs/batch",
        json={"project_id": project_id, "action": "pause"},
    ).json()
    assert paused["affected"] == 2
    assert paused["project_paused"] is True
    statuses = {job["job_id"]: job["status"] for job in paused["jobs"]}
    assert statuses[running.id] == STATUS_PAUSED
    assert statuses[queued.id] == STATUS_PAUSED

    resumed = client.post(
        "/api/jobs/batch",
        json={"project_id": project_id, "action": "resume"},
    ).json()
    assert resumed["affected"] == 2
    assert resumed["project_paused"] is False
    statuses = {job["job_id"]: job["status"] for job in resumed["jobs"]}
    assert statuses[running.id] == STATUS_QUEUED
    assert statuses[queued.id] == STATUS_QUEUED


def test_project_pause_holds_new_jobs_and_state_is_queryable(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    store = client.app.state.job_store

    before = client.get(
        "/api/jobs/project-state", params={"project_id": project_id}
    ).json()
    assert before == {"project_id": project_id, "paused": False}

    client.post(
        "/api/jobs/batch",
        json={"project_id": project_id, "action": "pause"},
    )
    held = _make_project_job(client, project_id)
    assert held.status == STATUS_PAUSED

    after = client.get(
        "/api/jobs/project-state", params={"project_id": project_id}
    ).json()
    assert after["paused"] is True


def test_project_resume_does_not_auto_resume_interrupted_job(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    store = client.app.state.job_store
    job = _make_project_job(client, project_id)
    store.mark_running(job.id)
    with get_connection(store.db_path) as conn:
        conn.execute(
            "UPDATE jobs SET heartbeat_at = '2020-01-01T00:00:00Z' WHERE id = ?",
            (job.id,),
        )
    store.recover_stale(stale_after_s=60)
    assert store.get(job.id).error_category == CATEGORY_INTERRUPTED

    store.pause_project(project_id)
    response = client.post(
        "/api/jobs/batch",
        json={"project_id": project_id, "action": "resume"},
    ).json()

    assert response["affected"] == 0
    assert response["project_paused"] is False
    assert store.get(job.id).status == STATUS_PAUSED


def test_batch_scope_exposes_metadata_and_only_controls_its_jobs(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    store = client.app.state.job_store
    first = store.create(
        "generation",
        project_id,
        capability="text_to_image",
        input_payload={
            "extra": {
                "batch_id": "batch_1",
                "batch_label": "第 1 集 · 场景 1",
                "target_id": "shot_1",
                "target_label": "场景 1 · 镜头 1",
            }
        },
    )
    other = store.create(
        "generation",
        project_id,
        capability="text_to_image",
        input_payload={"extra": {"batch_id": "batch_2"}},
    )

    listed = client.get("/api/jobs", params={"project_id": project_id}).json()
    item = next(job for job in listed if job["job_id"] == first.id)
    assert item["batch_label"] == "第 1 集 · 场景 1"
    assert item["target_id"] == "shot_1"

    response = client.post(
        "/api/jobs/batch",
        json={"project_id": project_id, "batch_id": "batch_1", "action": "cancel"},
    )
    assert response.json()["affected"] == 1
    assert store.get(first.id).status == STATUS_CANCELLED
    assert store.get(other.id).status == STATUS_QUEUED


def test_batch_retry_only_requeues_failed_jobs(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    store = client.app.state.job_store
    failed = store.create(
        "generation",
        project_id,
        input_payload={"extra": {"batch_id": "batch_1"}},
    )
    store.mark_running(failed.id)
    store.mark_failed(failed.id, "boom")
    cancelled = store.create(
        "generation",
        project_id,
        input_payload={"extra": {"batch_id": "batch_1"}},
    )
    store.cancel(cancelled.id)

    response = client.post(
        "/api/jobs/batch",
        json={"project_id": project_id, "batch_id": "batch_1", "action": "retry"},
    )
    assert response.json()["affected"] == 1
    assert store.get(failed.id).status == STATUS_QUEUED
    assert store.get(cancelled.id).status == STATUS_CANCELLED


def test_batch_unknown_stage_rejected(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    response = client.post(
        "/api/jobs/batch",
        json={"project_id": project_id, "action": "cancel", "stage": "nope"},
    )
    assert response.status_code == 422
