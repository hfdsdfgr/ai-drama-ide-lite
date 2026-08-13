"""模型列表拉取：OpenAI 兼容 /models 接口。"""

import httpx

from app.core.errors import AppError


def fetch_model_ids(base_url: str, api_key: str | None) -> list[str]:
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        with httpx.Client(timeout=20) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as exc:
        raise AppError(502, "discovery_timeout", "获取模型列表超时，请检查网络与 Base URL") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (401, 403):
            region_hint = (
                "；如为阿里云百炼，请确认 Key 所属站点与 Base URL 匹配（国内 dashscope.aliyuncs.com / 国际 dashscope-intl.aliyuncs.com）"
                if "dashscope" in base_url
                else ""
            )
            detail = f"API Key 无效或没有权限{region_hint}"
        else:
            detail = f"提供商返回 HTTP {status}"
        raise AppError(502, "discovery_failed", f"获取模型列表失败：{detail}") from exc
    except Exception as exc:
        raise AppError(502, "discovery_failed", "无法连接提供商，请检查 Base URL 与网络") from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise AppError(502, "discovery_invalid_response", "提供商返回格式不符合 /models 规范")
    ids = [
        item.get("id")
        for item in data
        if isinstance(item, dict) and item.get("id")
    ]
    if not ids:
        raise AppError(502, "discovery_empty", "提供商未返回任何模型")
    return ids
