"""LLM JSON 解析（共享）：去围栏 → json.loads → Pydantic 校验 → 一次修复重试。"""

import json
import re

from app.core.errors import AppError

_REPAIR_SYSTEM = (
    "你上一次输出的 JSON 无法通过解析。请只输出一个严格符合要求的 JSON 对象，"
    "不要解释、不要代码块标记。"
)


def extract_json(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        return fence.group(1)
    candidates: list[tuple[int, int, str]] = []
    for open_char, close_char in (("{", "}"), ("[", "]")):
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start >= 0 and end > start:
            candidates.append((start, end, open_char))
    if candidates:
        start, end, _open_char = min(candidates, key=lambda item: item[0])
        return text[start : end + 1]
    return text


def trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…（已截断）"


def parse_llm_json(model, text: str, chat, model_id: str, label: str):
    """chat 为 callable(model_id, messages, temperature=...)；失败时修复重试一次。"""
    for attempt in range(2):
        try:
            data = json.loads(extract_json(text))
            return model(**data)
        except Exception as exc:  # noqa: BLE001 - 需要把解析错误喂回模型
            if attempt == 0:
                text = chat(
                    model_id,
                    [
                        {"role": "system", "content": _REPAIR_SYSTEM},
                        {
                            "role": "user",
                            "content": (
                                f"上一次输出无法解析：{exc}\n"
                                f"原始输出：{trim(text, 3000)}\n"
                                "请重新输出符合要求的 JSON。"
                            ),
                        },
                    ],
                    temperature=0.1,
                )
            else:
                raise AppError(
                    502,
                    "llm_invalid_output",
                    f"{label}结果无法解析，请重试或更换模型",
                ) from exc
    raise AppError(502, "llm_invalid_output", f"{label}结果无法解析")
