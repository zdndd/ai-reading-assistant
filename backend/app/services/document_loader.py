from __future__ import annotations

from pathlib import Path

from app.core.errors import InvalidDocumentError

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown"}


def validate_document_name(file_name: str) -> str:
    safe_name = Path(file_name).name.strip()
    suffix = Path(safe_name).suffix.lower()
    if not safe_name or suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise InvalidDocumentError(f"仅支持以下文档格式：{allowed}")
    return safe_name


def decode_document(raw: bytes) -> tuple[str, str]:
    if not raw:
        raise InvalidDocumentError("文档内容为空")
    if b"\x00" in raw:
        raise InvalidDocumentError("文档不是受支持的纯文本格式")

    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise InvalidDocumentError("无法识别文档编码，请转换为 UTF-8 后重试")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise InvalidDocumentError("文档没有可索引的文本内容")
    return normalized, encoding
