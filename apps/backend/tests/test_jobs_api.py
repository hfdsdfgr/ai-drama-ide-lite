"""Phase 10 — 统一任务中心接口测试（/api/jobs）。"""

from app.services.job_store import (
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
