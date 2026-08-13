"""小说文本导入：编码探测 + TXT/Markdown/DOCX 解析为章节。"""

import io
from pathlib import Path

from app.core.errors import AppError


def decode_text(raw: bytes) -> str:
    """按常见编码顺序探测解码（见 DEVELOPMENT_PITFALLS.md：禁止假设固定编码）。"""
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def split_text_chapters(text: str, fallback_title: str) -> list[tuple[str, str]]:
    """按 Markdown 标题（# / ## / ###）切分章节；没有标题则整篇作为一章。"""
    chapters: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines or current_title:
            chapters.append(
                (current_title or fallback_title, "\n".join(current_lines).strip())
            )

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            hashes = len(stripped) - len(stripped.lstrip("#"))
            if hashes <= 3 and stripped[hashes : hashes + 1] in ("", " "):
                flush()
                current_title = stripped.lstrip("#").strip()
                current_lines = []
                continue
        current_lines.append(line)
    flush()
    return chapters or [(fallback_title, text.strip())]


def parse_docx_chapters(raw: bytes, fallback_title: str) -> list[tuple[str, str]]:
    """用 python-docx 解析 DOCX，按 Heading 样式切分章节。"""
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise AppError(500, "docx_library_missing", "DOCX 解析库未安装") from exc

    document = Document(io.BytesIO(raw))
    chapters: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines or current_title:
            chapters.append(
                (current_title or fallback_title, "\n".join(current_lines).strip())
            )

    for paragraph in document.paragraphs:
        style = (paragraph.style.name or "").lower()
        text = paragraph.text.strip()
        if style.startswith("heading"):
            flush()
            current_title = text or "未命名章节"
            current_lines = []
        elif text:
            current_lines.append(text)
    flush()
    if chapters:
        return chapters
    return [(fallback_title, "\n".join(current_lines).strip())]


def parse_novel_file(raw: bytes, filename: str) -> tuple[str, str, list[tuple[str, str]]]:
    """按扩展名解析导入文件，返回 (title, source_type, chapters)。"""
    name = Path(filename)
    ext = name.suffix.lower()
    fallback_title = name.stem.strip() or "导入小说"
    if ext in (".txt", ".md", ".markdown"):
        text = decode_text(raw)
        chapters = split_text_chapters(text, fallback_title)
        return fallback_title, "imported", chapters
    if ext == ".docx":
        chapters = parse_docx_chapters(raw, fallback_title)
        return fallback_title, "imported", chapters
    raise AppError(422, "unsupported_format", f"不支持的格式: {ext or '无扩展名'}")
