"""数据目录迁移测试。"""

from pathlib import Path

from app.services.data_migration import migrate_data_dir


def test_migrate_copies_legacy_data(tmp_path):
    base = tmp_path / "AI Drama IDE Lite"
    base.mkdir(parents=True)
    (base / "ai_drama_ide.db").write_bytes(b"db-bytes")
    (base / "projects").mkdir()
    (base / "projects" / "proj_1").write_text("{}")
    data_dir = base / "data"

    migrated = migrate_data_dir(data_dir, frozen=True)

    assert migrated is True
    assert (data_dir / "ai_drama_ide.db").read_bytes() == b"db-bytes"
    assert (data_dir / "projects" / "proj_1").is_file()
    # 源数据保留（只复制不删除）
    assert (base / "ai_drama_ide.db").exists()


def test_migrate_skips_when_current_exists(tmp_path):
    base = tmp_path / "AI Drama IDE Lite"
    base.mkdir(parents=True)
    (base / "ai_drama_ide.db").write_bytes(b"old")
    data_dir = base / "data"
    data_dir.mkdir()
    (data_dir / "ai_drama_ide.db").write_bytes(b"current")

    migrated = migrate_data_dir(data_dir, frozen=True)

    assert migrated is False
    assert (data_dir / "ai_drama_ide.db").read_bytes() == b"current"


def test_migrate_skips_development_mode(tmp_path):
    base = tmp_path / "AI Drama IDE Lite"
    base.mkdir(parents=True)
    (base / "ai_drama_ide.db").write_bytes(b"old")

    migrated = migrate_data_dir(base / "data", frozen=False)

    assert migrated is False


def test_migrate_no_legacy(tmp_path):
    data_dir = tmp_path / "data"
    migrated = migrate_data_dir(data_dir, frozen=True)
    assert migrated is False
