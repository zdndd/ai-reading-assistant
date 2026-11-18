from app.services.document_loader import decode_document
from app.services.text_splitter import TextSplitter


def test_decode_gb18030_document() -> None:
    source = "第一章\n这是 GB18030 编码的中文文本。"

    text, encoding = decode_document(source.encode("gb18030"))

    assert text == source
    assert encoding == "gb18030"


def test_splitter_keeps_boundaries_and_overlap() -> None:
    text = "第一句描述人物。" * 80
    splitter = TextSplitter(chunk_size=100, overlap=20)

    chunks = splitter.split(text)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 100 for chunk in chunks)
    assert chunks[0].end > chunks[1].start
    assert "第一句描述人物。" in chunks[0].text
