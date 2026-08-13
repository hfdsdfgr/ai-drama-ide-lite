"""项目导出 / 导入测试（含 zip-slip 防护）。"""

import io
import zipfile


def _export_zip(client, project_id):
    response = client.get(f"/api/projects/{project_id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    return response.content


def _import_zip(client, content):
    return client.post(
        "/api/projects/import",
        content=content,
        headers={"Content-Type": "application/zip"},
    )


def test_export_import_roundtrip(client):
    created = client.post(
        "/api/projects", json={"name": "往返项目", "description": "含文件"}
    ).json()
    project_id = created["id"]
    content = _export_zip(client, project_id)

    imported = _import_zip(client, content)
    assert imported.status_code == 201
    body = imported.json()
    assert body["id"] != project_id
    assert body["name"] == "往返项目"
    assert body["description"] == "含文件"


def test_export_import_preserves_novels(client):
    created = client.post(
        "/api/projects", json={"name": "往返项目", "description": "含小说"}
    ).json()
    project_id = created["id"]
    novel = client.post(
        f"/api/projects/{project_id}/novels", json={"title": "书中仙"}
    ).json()
    chapter = client.post(
        f"/api/projects/{project_id}/novels/{novel['id']}/chapters",
        json={"title": "第一章"},
    ).json()
    client.put(
        f"/api/projects/{project_id}/novels/{novel['id']}/chapters/{chapter['id']}",
        json={"content": "正文"},
    )

    content = _export_zip(client, project_id)
    imported = _import_zip(client, content)
    assert imported.status_code == 201
    imported_id = imported.json()["id"]

    novels = client.get(f"/api/projects/{imported_id}/novels").json()
    assert len(novels) == 1
    assert novels[0]["title"] == "书中仙"
    detail = client.get(
        f"/api/projects/{imported_id}/novels/{novels[0]['id']}"
    ).json()
    assert detail["chapters"][0]["content"] == "正文"


def test_export_import_preserves_files(client):
    created = client.post("/api/projects", json={"name": "带文件项目"}).json()
    project_id = created["id"]
    # 在项目目录里放一个真实文件
    settings = client.app.state.settings
    project_dir = settings.projects_dir / project_id
    novel_file = project_dir / "novel" / "chapter_01.txt"
    novel_file.parent.mkdir(parents=True, exist_ok=True)
    novel_file.write_text("第一章 测试内容", encoding="utf-8")

    content = _export_zip(client, project_id)
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = zf.namelist()
        assert "project.json" in names
        assert "files/novel/chapter_01.txt" in names

    imported = _import_zip(client, content)
    assert imported.status_code == 201
    imported_id = imported.json()["id"]
    imported_file = settings.projects_dir / imported_id / "novel" / "chapter_01.txt"
    assert imported_file.read_text(encoding="utf-8") == "第一章 测试内容"


def test_import_zip_slip_rejected(client):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "project.json",
            '{"schema_version":1,"project":{"name":"恶意包"}}',
        )
        zf.writestr("files/../../evil.txt", "boom")
    response = _import_zip(client, buffer.getvalue())
    assert response.status_code == 422
    assert response.json()["error"]["code"] in (
        "import_invalid_path",
        "import_invalid_entry",
    )


def test_import_missing_manifest(client):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("files/a.txt", "x")
    response = _import_zip(client, buffer.getvalue())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "import_invalid_manifest"


def test_import_invalid_zip(client):
    response = _import_zip(client, b"not a zip at all")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "import_invalid_zip"
