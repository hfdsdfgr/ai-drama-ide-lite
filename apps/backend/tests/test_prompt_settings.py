"""Offline prompt editing, project isolation, frozen rules and transfer safety."""

import io
import json
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.errors import AppError
from app.db.database import get_connection, init_db
from app.services.prompt_catalog import PROMPT_DEFINITIONS, get_definition
from app.services.prompt_settings import PromptSettingsService


def _project(client, name="提示词项目"):
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _stage(settings, stage_id):
    return next(stage for stage in settings["stages"] if stage["id"] == stage_id)


def _url(project_id, stage_id=""):
    return f"/api/projects/{project_id}/prompt-settings" + (f"/{stage_id}" if stage_id else "")


def _package(manifest):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("project.json", json.dumps(manifest, ensure_ascii=False))
    return buffer.getvalue()


def test_defaults_are_complete_and_offline(client, monkeypatch):
    project_id = _project(client)
    manager = client.app.state.provider_manager

    def fail(*args, **kwargs):
        pytest.fail("Saving or previewing prompt settings must never call a provider")

    monkeypatch.setattr(manager, "chat", fail)
    monkeypatch.setattr(manager, "generate", fail)
    defaults = client.get(_url(project_id)).json()
    assert defaults["revision"] == 0
    assert {stage["id"] for stage in defaults["stages"]} == set(PROMPT_DEFINITIONS)
    assert len(defaults["stages"]) == 22
    assert all(not stage["customized"] for stage in defaults["stages"])
    response = client.post(
        _url(project_id, "script_shots") + "/preview",
        json={"rules": "对话场景主要使用固定机位。"},
    )
    assert response.status_code == 200
    preview = response.json()
    assert preview["system_prompt"].startswith("对话场景主要使用固定机位。")
    assert "相邻镜头必须使用不同运镜" not in preview["system_prompt"]
    assert '"shots"' in preview["system_prompt"]
    assert "不可信数据" in preview["system_prompt"]
    assert preview["preview"] == preview["system_prompt"]
    assert client.get(_url(project_id)).json() == defaults
    with get_connection(client.app.state.settings.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM project_prompt_settings").fetchone()[0] == 0


def test_update_is_project_local_and_restorable(client):
    project_a, project_b = _project(client, "项目 A"), _project(client, "项目 B")
    result = client.put(
        _url(project_a, "script_shots"),
        json={"expected_revision": 0, "rules": "对话场景主要使用固定机位。"},
    )
    assert result.status_code == 200
    settings = result.json()
    assert settings["revision"] == 1
    assert _stage(settings, "script_shots")["customized"]
    assert not _stage(client.get(_url(project_b)).json(), "script_shots")["customized"]
    conflict = client.put(
        _url(project_a, "novel_outline"), json={"expected_revision": 0, "rules": "短篇故事"}
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "prompt_revision_conflict"
    restored = client.put(
        _url(project_a, "script_shots"), json={"expected_revision": 1, "rules": None}
    ).json()
    assert restored["revision"] == 2
    assert not _stage(restored, "script_shots")["customized"]


def test_empty_media_rules_and_negative_semantics(client):
    project_id = _project(client)
    url = _url(project_id, "image_character")
    first = client.put(url, json={"expected_revision": 0, "rules": "", "negative_prompt": ""})
    assert first.status_code == 200
    values = _stage(first.json(), "image_character")
    assert values["rules"] == values["negative_prompt"] == ""
    assert values["customized"]
    second = client.put(url, json={"expected_revision": 1, "rules": "水墨人像"}).json()
    assert _stage(second, "image_character")["negative_prompt"] == ""
    third = client.put(
        url, json={"expected_revision": 2, "rules": "水墨人像", "negative_prompt": None}
    ).json()
    default = get_definition("image_character").default_negative_prompt
    assert _stage(third, "image_character")["negative_prompt"] == default
    restored = client.put(url, json={"expected_revision": 3, "rules": None}).json()
    assert not _stage(restored, "image_character")["customized"]
    assert _stage(restored, "image_character")["negative_prompt"] == default


@pytest.mark.parametrize("payload", [
    {"expected_revision": 0, "rules": ""},
    {"expected_revision": 0, "rules": "  \n"},
    {"expected_revision": 0, "rules": "x" * 12001},
    {"expected_revision": "0", "rules": "规则"},
    {"expected_revision": True, "rules": "规则"},
    {"expected_revision": -1, "rules": "规则"},
    {"expected_revision": 0, "rules": 123},
    {"expected_revision": 0, "rules": "规则", "negative_prompt": "不允许"},
    {"expected_revision": 0, "rules": "规则", "contract": "不能编辑格式"},
    {"expected_revision": 0},
])
def test_invalid_text_settings_rejected(client, payload):
    project_id = _project(client)
    response = client.put(_url(project_id, "script_shots"), json=payload)
    assert response.status_code == 422
    assert client.get(_url(project_id)).json()["revision"] == 0


def test_invalid_media_negative_and_preview_rejected(client):
    project_id = _project(client)
    url = _url(project_id, "image_shot")
    for negative in ("x" * 1001, 42, []):
        payload = {"rules": "", "negative_prompt": negative}
        assert client.put(url, json={"expected_revision": 0, **payload}).status_code == 422
        assert client.post(url + "/preview", json=payload).status_code == 422
    assert client.post(
        _url(project_id, "novel_chapter") + "/preview", json={"rules": " "}
    ).status_code == 422


def test_missing_project_stage_and_deleted_project_rejected(client):
    assert client.get(_url("proj_missing")).status_code == 404
    project_id = _project(client)
    assert client.put(
        _url(project_id, "made_up_stage"), json={"expected_revision": 0, "rules": "规则"}
    ).status_code == 404
    assert client.post(
        _url(project_id, "made_up_stage") + "/preview", json={"rules": "规则"}
    ).status_code == 404
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(_url(project_id)).status_code == 404


def test_snapshot_is_detached_and_contract_variants_are_fixed(client):
    project_id = _project(client)
    service = PromptSettingsService(client.app.state.settings.db_path)
    service.update(project_id, "novel_chapter", 0, "只写一百字。")
    snapshot = service.snapshot(project_id)
    service.update(project_id, "novel_chapter", 1, "只写五百字。")
    current = service.system_prompt(project_id, "novel_chapter")
    frozen = service.system_prompt(project_id, "novel_chapter", snapshot)
    stream = service.system_prompt(project_id, "novel_chapter", snapshot, variant="stream")
    assert current.startswith("只写五百字。")
    assert frozen.startswith("只写一百字。")
    assert "2000-4000" not in frozen
    assert '"title"' in frozen and '"content"' in frozen
    assert stream.startswith("只写一百字。") and "不要输出 JSON" in stream
    assert '"content"' not in stream
    assert snapshot["revision"] == 1
    assert service.system_prompt("", "novel_chapter", {"stages": {}}).startswith(
        get_definition("novel_chapter").default_rules
    )
    with pytest.raises(AppError, match="输出格式"):
        service.system_prompt(project_id, "novel_chapter", variant="unsupported")


def test_concurrent_revision_updates_do_not_overwrite(client):
    project_id = _project(client)
    db_path = client.app.state.settings.db_path

    def save(rules):
        try:
            PromptSettingsService(db_path).update(project_id, "script_shots", 0, rules)
            return "saved"
        except AppError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["方案 A", "方案 B"]))
    assert sorted(results) == ["prompt_revision_conflict", "saved"]
    assert PromptSettingsService(db_path).snapshot(project_id)["revision"] == 1


def test_project_export_import_preserves_settings_without_remapping_prompt_text(client):
    project_id = _project(client)
    service = PromptSettingsService(client.app.state.settings.db_path)
    with get_connection(client.app.state.settings.db_path) as conn:
        conn.execute(
            "INSERT INTO scenes (id, project_id, title, created_at, updated_at) VALUES ('scene_1', ?, '场景', 'now', 'now')",
            (project_id,),
        )
    service.update(project_id, "image_shot", 0, "scene_1 是我的创作词，不要改写。", "")
    exported = client.get(f"/api/projects/{project_id}/export")
    assert exported.status_code == 200
    for _ in range(2):
        imported = client.post(
            "/api/projects/import", content=exported.content,
            headers={"Content-Type": "application/zip"},
        )
        assert imported.status_code == 201
        imported_id = imported.json()["id"]
        assert imported_id != project_id
        settings = service.list_settings(imported_id)
        values = _stage(settings, "image_shot")
        assert settings["revision"] == 1
        assert values["rules"] == "scene_1 是我的创作词，不要改写。"
        assert values["negative_prompt"] == ""
        with get_connection(client.app.state.settings.db_path) as conn:
            scene = conn.execute("SELECT id FROM scenes WHERE project_id = ?", (imported_id,)).fetchone()
            assert scene["id"] != "scene_1"


@pytest.mark.parametrize("version", [1, 2, 3])
def test_old_project_packages_use_default_settings(client, version):
    manifest = {"schema_version": version, "project": {"name": "旧项目"}}
    if version == 3:
        manifest["snapshot"] = {"novels": []}
    imported = client.post(
        "/api/projects/import", content=_package(manifest),
        headers={"Content-Type": "application/zip"},
    )
    assert imported.status_code == 201
    settings = client.get(_url(imported.json()["id"])).json()
    assert settings["revision"] == 0
    assert all(not stage["customized"] for stage in settings["stages"])


@pytest.mark.parametrize("row", [
    {"revision": -1, "overrides_json": "{}"},
    {"revision": True, "overrides_json": "{}"},
    {"overrides_json": "invalid json"},
    {"overrides_json": '{"made_up_stage": {"rules": "x"}}'},
    {"overrides_json": '{"script_shots": {"rules": ""}}'},
    {"overrides_json": '{"script_shots": {"contract": "change format"}}'},
    {"overrides_json": "{}", "id": "unexpected_primary_key"},
    {"overrides_json": "{}", "rules) VALUES ('injected'); --": "invalid_column"},
])
def test_invalid_imported_settings_rejected_before_creating_project(client, row):
    manifest = {
        "schema_version": 3, "project": {"name": "坏配置"},
        "snapshot": {"project_prompt_settings": [row]},
    }
    response = client.post(
        "/api/projects/import", content=_package(manifest),
        headers={"Content-Type": "application/zip"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "import_invalid_prompt_settings"
    assert client.get("/api/projects").json() == []


def test_schema_upgrade_adds_settings_without_overwriting_project(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""CREATE TABLE projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT)""")
        conn.execute("INSERT INTO projects VALUES ('proj_old','原项目','', 'old','old',NULL)")
    init_db(db_path)
    init_db(db_path)
    assert PromptSettingsService(db_path).list_settings("proj_old")["revision"] == 0
    with get_connection(db_path) as conn:
        assert conn.execute("SELECT name FROM projects WHERE id='proj_old'").fetchone()[0] == "原项目"
