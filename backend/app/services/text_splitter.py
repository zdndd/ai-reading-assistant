from __future__ import annotations

from app.domain.documents import ChunkDraft

BOUNDARY_CHARACTERS = ("。", "！", "？", "；", ".", "!", "?", ";", "\n")


class TextSplitter:
    def __init__(self, chunk_size: int = 300, overlap: int = 50) -> None:
        if overlap >= chunk_size:
            raise ValueError("overlap 必须小于 chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkDraft]:
        chunks: list[ChunkDraft] = []
        start = 0
        text_length = len(text)

        while start < text_length:
            target_end = min(start + self.chunk_size, text_length)
            end = self._find_boundary(text, start, target_end)
            left = start
            right = end
            while left < right and text[left].isspace():
                left += 1
            while right > left and text[right - 1].isspace():
                right -= 1
            if left < right:
                chunks.append(ChunkDraft(text=text[left:right], start=left, end=right))

            if end >= text_length:
                break
            start = max(end - self.overlap, start + 1)

        return chunks

    def _find_boundary(self, text: str, start: int, target_end: int) -> int:
        if target_end >= len(text):
            return len(text)

        boundary = max(text.rfind(char, start, target_end) for char in BOUNDARY_CHARACTERS)
        if boundary >= start + self.chunk_size // 2:
            return boundary + 1
        return target_end
