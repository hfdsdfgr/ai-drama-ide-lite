"""Project lifecycle tests (Phase 0 completion criteria)."""


def test_project_create_save_reopen(client):
    # 创建
    response = client.post(
        "/api/projects",
        json={"name": "测试项目", "description": "Phase 0 冒烟测试"},
    )
    assert response.status_code == 201
    project = response.json()
    project_id = project["id"]
    assert project["name"] == "测试项目"

    # 重新打开（列表）
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert any(item["id"] == project_id for item in response.json())

    # 重新打开（单个）
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "测试项目"

    # 保存（更新）
    response = client.put(
        f"/api/projects/{project_id}", json={"description": "已保存"}
    )
    assert response.status_code == 200
    assert response.json()["description"] == "已保存"

    # 重新打开后数据仍在（持久化）
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["description"] == "已保存"


def test_project_not_found(client):
    response = client.get("/api/projects/proj_does_not_exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


def test_invalid_project_id_rejected(client):
    # 非法 ID（含空格）应被拒绝，防止路径遍历
    response = client.get("/api/projects/bad%20id%21")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_project_id"


def test_validation_error_message(client):
    response = client.post("/api/projects", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
