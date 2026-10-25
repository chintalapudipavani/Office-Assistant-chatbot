"""Turn text into vectors with a local Sentence Transformers model."""
import logging
import threading

import numpy as np
from django.conf import settings

from .exceptions import EmbeddingError

logger = logging.getLogger(__name__)
_model = None
_lock = threading.Lock()


def get_model():
    """Load the model once (first call downloads ~90 MB) and reuse it."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    logger.info("Loading embedding model %s", settings.EMBEDDING_MODEL_NAME)
                    _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
                except Exception as exc:
                    logger.exception("Could not load embedding model")
                    raise EmbeddingError() from exc
    return _model


def embed_texts(texts, batch_size=32):
    """Return a float32 array (n, dim) of L2-normalised vectors.
    Normalised vectors make inner product equal cosine similarity (0..1 here)."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = get_model()
    try:
        vectors = model.encode(
            list(texts), batch_size=batch_size, convert_to_numpy=True,
            normalize_embeddings=True, show_progress_bar=False,
        )
    except Exception as exc:
        logger.exception("Embedding failed")
        raise EmbeddingError("Embedding the text failed. See the server log for details.") from exc
    return np.asarray(vectors, dtype=np.float32)


def embed_query(question):
    return embed_texts([question])[0]
