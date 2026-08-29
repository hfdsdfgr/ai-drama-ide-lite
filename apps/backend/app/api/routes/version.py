"""版本信息与更新检查 API。"""

import httpx
from fastapi import APIRouter, Request

from app.version import APP_VERSION

router = APIRouter(prefix="/api/version", tags=["version"])

_UPDATE_URL = "https://api.github.com/repos/hfdsdfgr/ai-drama-ide-lite/releases/latest"


@router.get("", response_model=dict)
def get_version(request: Request) -> dict:
    return {
        "app_name": request.app.state.settings.app_name,
        "version": APP_VERSION,
    }


def _parse_version(value: str) -> tuple[int, ...]:
    parts = []
    for part in value.strip().lstrip("v").split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


@router.get("/check", response_model=dict)
def check_version() -> dict:
    """检查 GitHub 最新 Release 版本（容错：网络失败返回 latest=None，不阻塞应用）。"""
    try:
        with httpx.Client(timeout=6) as client:
            response = client.get(_UPDATE_URL)
            response.raise_for_status()
            data = response.json()
        latest = str(data.get("tag_name") or "").lstrip("v")
        if not latest:
            return {
                "current": APP_VERSION,
                "latest": None,
                "has_update": False,
                "error": "更新服务器未返回版本号",
            }
        return {
            "current": APP_VERSION,
            "latest": latest,
            "has_update": _parse_version(latest) > _parse_version(APP_VERSION),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - 网络异常统一容错
        return {
            "current": APP_VERSION,
            "latest": None,
            "has_update": False,
            "error": f"无法连接更新服务器：{exc.__class__.__name__}",
        }
