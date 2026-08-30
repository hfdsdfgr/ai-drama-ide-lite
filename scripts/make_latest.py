# -*- coding: utf-8 -*-
"""CI 用：扫描构建产物目录生成 Tauri updater 的 latest.json。

用法：python3 scripts/make_latest.py <artifacts_dir> <tag> <owner/repo>
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    artifacts_dir = Path(sys.argv[1])
    tag = sys.argv[2].lstrip("v")
    repo = sys.argv[3]

    platforms: dict = {}
    for exe in artifacts_dir.rglob("*.exe"):
        m = re.match(
            r"ai-drama-ide-lite-windows-([a-z0-9_]+)-setup\.exe", exe.name
        )
        if not m:
            continue
        sig = Path(str(exe) + ".sig")
        if not sig.exists():
            print(f"WARN: missing sig for {exe.name}")
            continue
        arch = m.group(1)
        platforms[f"windows-{arch}"] = {
            "url": f"https://github.com/{repo}/releases/download/v{tag}/{exe.name}",
            "signature": sig.read_text(encoding="utf-8", errors="replace").strip(),
        }

    # macOS updater 产物是 .app.tar.gz（首次安装用 dmg，自动更新用 tar.gz）
    for targz in artifacts_dir.rglob("*.app.tar.gz"):
        m = re.match(r"ai-drama-ide-lite-macos-([a-z0-9]+)\.app\.tar\.gz", targz.name)
        if not m:
            continue
        sig = Path(str(targz) + ".sig")
        if not sig.exists():
            print(f"WARN: missing sig for {targz.name}")
            continue
        arch = m.group(1)  # aarch64 / x86_64
        platforms[f"darwin-{arch}"] = {
            "url": f"https://github.com/{repo}/releases/download/v{tag}/{targz.name}",
            "signature": sig.read_text(encoding="utf-8", errors="replace").strip(),
        }

    latest = {
        "version": tag,
        "notes": f"v{tag}",
        "pub_date": datetime.now(timezone.utc).isoformat(),
        "platforms": platforms,
    }
    Path("latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("platforms:", list(platforms.keys()))


if __name__ == "__main__":
    main()
