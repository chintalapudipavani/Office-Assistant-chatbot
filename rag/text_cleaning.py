"""Clean raw PDF text so that chunks are tidy and searchable."""
import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(text):
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00ad", "")                 # soft hyphens
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)       # re-join words split by line-end hyphens
    text = _CONTROL.sub("", text)
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
