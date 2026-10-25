"""Split page text into overlapping chunks, preferring paragraph/sentence boundaries."""
import re

_WHITESPACE = re.compile(r"\s")


def split_text(text, chunk_size=800, overlap=150):
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if cut > chunk_size * 0.5:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        next_start = max(end - overlap, start + 1)
        match = _WHITESPACE.search(text, next_start)   # do not start in the middle of a word
        if match and match.start() < end:
            next_start = match.start() + 1
        start = next_start
    return chunks
