"""FAISS vector index with atomic persistence.

The index is saved to one file (settings.RAG_INDEX_PATH). It is a rebuildable cache:
the database table DocumentChunk is the source of truth.
Vectors are stored with the chunk's database id as their FAISS id.
"""
import logging
import os
import threading

import numpy as np
from django.conf import settings

from .exceptions import VectorStoreError

logger = logging.getLogger(__name__)
_lock = threading.RLock()
_index = None
_loaded_mtime = None


def _faiss():
    try:
        import faiss
    except Exception as exc:
        raise VectorStoreError("The FAISS library could not be loaded. Reinstall faiss-cpu.") from exc
    return faiss


def _path():
    return settings.RAG_INDEX_PATH


def _file_mtime():
    try:
        return os.stat(_path()).st_mtime_ns
    except FileNotFoundError:
        return None


def reset_cache():
    global _index, _loaded_mtime
    with _lock:
        _index = None
        _loaded_mtime = None


def _get_index():
    """Return the in-memory index, reloading it if another process changed the file."""
    global _index, _loaded_mtime
    with _lock:
        mtime = _file_mtime()
        if _index is not None and mtime == _loaded_mtime:
            return _index
        if mtime is None:
            _index, _loaded_mtime = None, None
            return None
        faiss = _faiss()
        try:
            data = np.frombuffer(_path().read_bytes(), dtype=np.uint8)
            _index = faiss.deserialize_index(data)
        except Exception as exc:
            _index, _loaded_mtime = None, None
            logger.exception("Damaged index file")
            raise VectorStoreError(
                "The search index file is damaged. An administrator should click 'Rebuild index'."
            ) from exc
        _loaded_mtime = mtime
        return _index


def _save(index):
    """Write to a temporary file, then replace the real file (atomic)."""
    global _index, _loaded_mtime
    faiss = _faiss()
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    data = faiss.serialize_index(index)
    with open(tmp, "wb") as fh:
        fh.write(data.tobytes())
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    _index = index
    _loaded_mtime = _file_mtime()


def size():
    with _lock:
        index = _get_index()
        return 0 if index is None else int(index.ntotal)


def add_vectors(ids, vectors):
    faiss = _faiss()
    vectors = np.ascontiguousarray(vectors, dtype=np.float32)
    if vectors.ndim != 2 or len(ids) != vectors.shape[0] or len(ids) == 0:
        raise VectorStoreError("Internal error: ids and vectors do not match.")
    with _lock:
        index = _get_index()
        if index is None:
            index = faiss.IndexIDMap(faiss.IndexFlatIP(vectors.shape[1]))
        elif index.d != vectors.shape[1]:
            raise VectorStoreError(
                "The index was built with a different embedding model. Click 'Rebuild index' "
                "after re-uploading your documents."
            )
        try:
            index.add_with_ids(vectors, np.asarray(ids, dtype=np.int64))
            _save(index)
        except Exception as exc:
            reset_cache()
            logger.exception("Could not update index")
            raise VectorStoreError() from exc


def replace_all(ids, vectors):
    """Build a brand-new index from scratch and swap it in atomically."""
    faiss = _faiss()
    with _lock:
        if not ids:
            reset_cache()
            try:
                _path().unlink()
            except FileNotFoundError:
                pass
            return
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        index = faiss.IndexIDMap(faiss.IndexFlatIP(vectors.shape[1]))
        try:
            index.add_with_ids(vectors, np.asarray(ids, dtype=np.int64))
            _save(index)
        except Exception as exc:
            reset_cache()
            logger.exception("Could not rebuild index")
            raise VectorStoreError() from exc


def search(query_vector, k):
    """Return [(chunk_id, score), ...] best first. Score = cosine similarity."""
    with _lock:
        index = _get_index()
        if index is None or index.ntotal == 0:
            return []
        q = np.ascontiguousarray(np.asarray(query_vector, dtype=np.float32).reshape(1, -1))
        if q.shape[1] != index.d:
            raise VectorStoreError(
                "The index and the embedding model do not match. An administrator should rebuild the index."
            )
        scores, ids = index.search(q, min(int(k), int(index.ntotal)))
    return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]
