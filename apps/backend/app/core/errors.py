"""Application error types and FastAPI exception handlers."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .logging import get_logger

logger = get_logger("errors")

# 常见请求字段 -> 中文名（用于把 422 校验错误转成用户可读的提示）
_FIELD_LABELS = {
    "title": "标题",
    "name": "名称",
    "description": "描述",
    "content": "内容",
    "model_id": "模型",
    "model_type": "模型类型",
    "provider_id": "Provider",
    "provider_name": "Provider 名称",
    "preset_key": "厂商预设",
    "base_url": "Base URL",
    "api_key": "API Key",
    "project_id": "项目",
    "novel_id": "小说",
    "chapter_id": "章节",
    "filename": "文件名",
    "capability": "能力",
    "capabilities": "能力列表",
    "prompt": "提示词",
    "aspect_ratio": "画面比例",
    "duration": "视频时长",
    "genre": "题材",
    "audience": "受众",
    "ideas": "初步想法",
    "complexity": "情节复杂程度",
    "chapter_count": "章节数",
    "chapter_index": "章节索引",
    "user_instruction": "对本章的要求",
    "mode": "分析模式",
    "model_ids": "模型列表",
    "q": "搜索关键词",
    "url": "地址",
}


def _describe_validation_error(err: dict) -> str:
    """把单个 Pydantic 校验错误转成面向用户的中文提示。"""
    loc = err.get("loc") or []
    field = str(loc[-1]) if loc else ""
    label = _FIELD_LABELS.get(field, field or "参数")
    etype = str(err.get("type") or "")
    raw = str(err.get("msg") or "")
    if etype == "missing":
        return f"缺少参数「{label}」"
    if etype == "string_too_short":
        return f"「{label}」不能为空"
    if etype == "string_too_long":
        return f"「{label}」超出长度限制"
    if etype in ("int_type", "int_parsing"):
        return f"「{label}」必须是整数"
    if etype in ("greater_than", "greater_than_equal"):
        return f"「{label}」数值过小"
    if etype in ("less_than", "less_than_equal"):
        return f"「{label}」数值过大"
    if etype in ("bool_type", "bool_parsing"):
        return f"「{label}」必须是是/否"
    if etype == "literal_error":
        return f"「{label}」取值不合法"
    if etype in (
        "string_type",
        "value_error",
        "json_invalid",
        "model_attributes_type",
    ):
        return f"「{label}」格式不正确"
    return f"「{label}」校验失败：{raw}"


class AppError(Exception):
    """业务错误：携带 HTTP 状态码与机器可读错误码，错误信息面向用户可操作。"""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        messages = [_describe_validation_error(e) for e in errors]
        message = "；".join(messages[:3])
        if len(messages) > 3:
            message += f"（共 {len(messages)} 处）"
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": message,
                    "details": errors,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "服务器内部错误，请查看日志",
                }
            },
        )
