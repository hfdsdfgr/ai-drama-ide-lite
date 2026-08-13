"""OpenAI 兼容 LLM 客户端（单次调用，无并行）。"""

import httpx

from app.core.errors import AppError


def chat_completion(
    base_url: str,
    api_key: str | None,
    model: str,
    messages: list[dict],
    timeout: int = 60,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    payload = {"model": model, "messages": messages, "temperature": 0.8}
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise AppError(502, "llm_timeout", "模型响应超时，请重试或更换模型") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (401, 403):
            detail = "API Key 无效或没有权限"
        elif status == 404:
            detail = "模型不存在或未开通"
        elif status == 429:
            detail = "触发限流或额度不足"
        else:
            detail = f"提供商返回 HTTP {status}"
        raise AppError(502, "llm_failed", f"文本生成失败：{detail}") from exc
    except Exception as exc:
        raise AppError(502, "llm_failed", "无法连接提供商，请检查网络与配置") from exc

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AppError(502, "llm_invalid_response", "提供商返回格式异常") from exc
