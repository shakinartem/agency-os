"""Knowledge Base ingestion primitives."""

from app.services.knowledge import checksum_text, chunk_text, normalize_text


def test_normalize_text_is_stable_and_removes_nuls():
    value = normalize_text("  First line\r\nSecond\x00 line  \r\n\r\nThird line  ")
    assert "\x00" not in value
    assert "First line" in value
    assert "Second  line" in value
    assert value.endswith("Third line")


def test_checksum_is_stable_for_same_normalized_text():
    text = normalize_text("Product facts and positioning.\nThis is enough readable context.")
    assert checksum_text(text) == checksum_text(text)
    assert len(checksum_text(text)) == 64


def test_chunking_is_bounded_and_overlapping():
    text = " ".join(f"word{i}" for i in range(1200))
    chunks = chunk_text(text)
    assert len(chunks) > 2
    assert all(chunk.strip() for chunk in chunks)
    # Chunker may extend a little around boundaries but must remain around configured size.
    assert max(len(chunk) for chunk in chunks) <= 1500
    # Overlap should preserve context between neighboring chunks.
    assert any(token in chunks[1] for token in chunks[0].split()[-20:])
