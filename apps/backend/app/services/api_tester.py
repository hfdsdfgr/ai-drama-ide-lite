"""API 连接测试（Phase 4 — L1 连接 / L2 鉴权 / 模型可用性）。

参考 Open WebUI（/models 验证连接 + allowlist 手动兜底）与 SillyTavern
（错误信息必须可操作：指明哪个 Provider、什么错误）。
L1/L2 零成本；真实生成测试（L3）留到 Phase 5 且需用户确认费用。
"""

from datetime import datetime, timezone

import httpx

from app.schemas.provider import (
    ModelCheckOut,
    ProviderCheckOut,
    ProviderTestOut,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _network_detail(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "连接超时：请检查网络、Base URL 或代理设置"
    if isinstance(exc, httpx.ConnectError):
        return "无法建立连接：请检查 Base URL 是否可访问"
    if isinstance(exc, httpx.HTTPError):
        return f"HTTP 请求失败：{exc}"
    return f"请求异常：{exc}"


def _fetch_models(
    base_url: str, api_key: str | None, protocol: str = "openai_compat"
) -> tuple[str, str, list[str]]:
    """请求 /models。返回 (status, detail, ids)；status: ok|auth_fail|endpoint_missing|http_error|network_error。"""
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001 - 需要区分网络层错误
        return "network_error", _network_detail(exc), []

    status = response.status_code
    if status in (401, 403):
        return (
            "auth_fail",
            f"鉴权失败（HTTP {status}）：API Key 无效或没有权限",
            [],
        )
    if status == 404:
        return (
            "endpoint_missing",
            "接口不存在（HTTP 404）：请检查 Base URL 是否以 /v1 结尾或路径是否正确",
            [],
        )
    if status >= 400:
        return "http_error", f"提供商返回 HTTP {status}", []
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        return "http_error", "响应不是有效 JSON，接口可能不是 OpenAI 兼容格式", []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return "http_error", "响应缺少 data 列表，接口可能不是 OpenAI 兼容格式", []
    ids = [
        item.get("id")
        for item in data
        if isinstance(item, dict) and item.get("id")
    ]
    return "ok", f"连接成功，返回 {len(ids)} 个模型", ids


def run_provider_test(
    provider_id: str,
    base_url: str,
    api_key: str | None,
    needs_key: bool,
    has_key: bool,
    discoverable: bool,
    models: list,
    protocol: str = "openai_compat",
) -> ProviderTestOut:
    """执行 L1/L2 测试；models 为已启用模型列表（任意含 model_id 的对象）。"""
    checks: list[ProviderCheckOut] = []
    model_checks: list[ModelCheckOut] = []

    if not base_url.strip():
        checks.append(
            ProviderCheckOut(label="配置检查", status="fail", detail="未设置 Base URL")
        )
        return ProviderTestOut(
            provider_id=provider_id,
            ok=False,
            checks=checks,
            tested_at=_now_iso(),
        )
    if needs_key and not has_key:
        checks.append(
            ProviderCheckOut(
                label="配置检查",
                status="fail",
                detail="未配置 API Key，请先在「编辑」中填写",
            )
        )
        return ProviderTestOut(
            provider_id=provider_id,
            ok=False,
            checks=checks,
            tested_at=_now_iso(),
        )

    if discoverable:
        status, detail, ids = _fetch_models(base_url, api_key, protocol)
        if status == "network_error":
            checks.append(
                ProviderCheckOut(
                    label="连接测试（Endpoint）", status="fail", detail=detail
                )
            )
            checks.append(
                ProviderCheckOut(
                    label="鉴权测试（API Key）",
                    status="skipped",
                    detail="因连接失败跳过",
                )
            )
        elif status == "auth_fail":
            checks.append(
                ProviderCheckOut(
                    label="连接测试（Endpoint）",
                    status="ok",
                    detail=f"已连接 {base_url}",
                )
            )
            checks.append(
                ProviderCheckOut(
                    label="鉴权测试（API Key）", status="fail", detail=detail
                )
            )
        elif status == "endpoint_missing":
            checks.append(
                ProviderCheckOut(
                    label="连接测试（Endpoint）",
                    status="ok",
                    detail=f"已连接 {base_url}",
                )
            )
            checks.append(
                ProviderCheckOut(
                    label="鉴权测试（API Key）", status="skipped", detail=detail
                )
            )
        elif status == "http_error":
            checks.append(
                ProviderCheckOut(
                    label="连接测试（Endpoint）",
                    status="ok",
                    detail=f"已连接 {base_url}",
                )
            )
            checks.append(
                ProviderCheckOut(
                    label="鉴权测试（API Key）", status="fail", detail=detail
                )
            )
        else:
            checks.append(
                ProviderCheckOut(
                    label="连接测试（Endpoint）",
                    status="ok",
                    detail=f"已连接 {base_url}",
                )
            )
            checks.append(
                ProviderCheckOut(
                    label="鉴权测试（API Key）", status="ok", detail=detail
                )
            )
            if models:
                missing = [m.model_id for m in models if m.model_id not in ids]
                for m in models:
                    model_checks.append(
                        ModelCheckOut(
                            model_id=m.model_id,
                            ok=m.model_id in ids,
                            detail=(
                                "模型可用"
                                if m.model_id in ids
                                else "该模型不在 /models 返回列表中"
                            ),
                        )
                    )
                if missing:
                    checks.append(
                        ProviderCheckOut(
                            label="模型可用性",
                            status="fail",
                            detail=(
                                f"{len(missing)} 个模型不在列表中："
                                f"{', '.join(missing[:5])}"
                                + ("…" if len(missing) > 5 else "")
                            ),
                        )
                    )
                else:
                    checks.append(
                        ProviderCheckOut(
                            label="模型可用性",
                            status="ok",
                            detail=f"已启用模型全部存在（{len(models)} 个）",
                        )
                    )
            else:
                checks.append(
                    ProviderCheckOut(
                        label="模型可用性",
                        status="skipped",
                        detail="该 Provider 下还没有模型，可先拉取或手动添加",
                    )
                )
    else:
        # 非 discoverable（如百炼）：只做可达性 + 配置检查，模型级校验跳过
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(base_url.rstrip("/") + "/")
        except Exception as exc:  # noqa: BLE001
            checks.append(
                ProviderCheckOut(
                    label="连接测试（Endpoint）",
                    status="fail",
                    detail=_network_detail(exc),
                )
            )
        else:
            checks.append(
                ProviderCheckOut(
                    label="连接测试（Endpoint）",
                    status="ok",
                    detail=f"已连接 {base_url}（HTTP {response.status_code}）",
                )
            )
        checks.append(
            ProviderCheckOut(
                label="鉴权测试（API Key）",
                status="skipped",
                detail="该厂商不支持模型列表校验；密钥将在首次实际调用时验证",
            )
        )
        checks.append(
            ProviderCheckOut(
                label="模型可用性",
                status="skipped",
                detail="能力以规则推断 + 手动覆盖为准",
            )
        )

    ok = all(c.status != "fail" for c in checks)
    return ProviderTestOut(
        provider_id=provider_id,
        ok=ok,
        checks=checks,
        model_checks=model_checks,
        tested_at=_now_iso(),
    )
