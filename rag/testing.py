"""Helpers for automated tests ONLY. Uses a tiny word-hashing embedder instead of the real
Sentence Transformers model, so tests run in seconds without downloads."""
import hashlib
import re
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pymupdf
from django.test import TestCase, override_settings

from . import embeddings, vector_store

DIM = 384
_STOP = {"the", "a", "an", "is", "are", "how", "many", "do", "i", "to", "of", "my", "what", "for",
         "per", "in", "and", "can", "does", "get", "me", "it", "on", "be", "or", "if", "at"}


def fake_embed_texts(texts, batch_size=32):
    rows = []
    for text in texts:
        vec = np.zeros(DIM, dtype=np.float32)
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            if token in _STOP:
                continue
            vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = np.linalg.norm(vec)
        rows.append(vec / norm if norm else vec)
    return np.vstack(rows).astype(np.float32) if rows else np.zeros((0, DIM), dtype=np.float32)


def fake_embed_query(question):
    return fake_embed_texts([question])[0]


def make_pdf_bytes(pages):
    """pages: list of strings, one per page ('' makes a blank page)."""
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


class RagTestCase(TestCase):
    """Temporary media folder + index file, fake embedder, fake API key."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp()
        self._override = override_settings(
            MEDIA_ROOT=Path(self._tmp) / "media",
            RAG_INDEX_PATH=Path(self._tmp) / "faiss.index",
            RETRIEVAL_MIN_SCORE=0.15,
            LLM_API_KEY="test-key",
        )
        self._override.enable()
        self._patches = [
            mock.patch.object(embeddings, "embed_texts", fake_embed_texts),
            mock.patch.object(embeddings, "embed_query", fake_embed_query),
        ]
        for p in self._patches:
            p.start()
        vector_store.reset_cache()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._override.disable()
        vector_store.reset_cache()
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()
