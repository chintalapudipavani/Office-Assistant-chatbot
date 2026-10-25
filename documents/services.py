"""Ingestion: extract -> clean -> chunk -> embed -> save chunks -> update the FAISS index."""
import logging

from django.conf import settings
from django.db import transaction

from rag import chunker, embeddings, pdf_loader, prompts, text_cleaning, vector_store
from rag.exceptions import EmptyPDFError, RAGError, VectorStoreError

from .models import Document, DocumentChunk

logger = logging.getLogger(__name__)


def _mark_failed(document, message):
    document.chunks.all().delete()
    document.status = Document.Status.FAILED
    document.error_message = message
    document.chunk_count = 0
    document.save()


def process_document(document):
    """Process one uploaded Document. Never raises: problems are stored on the document."""
    document.status = Document.Status.PROCESSING
    document.error_message = ""
    document.save()
    try:
        pages = pdf_loader.extract_pages(document.file.path)
        pieces = []   # (page_number, text)
        for page_number, raw in pages:
            cleaned = text_cleaning.clean_text(raw)
            for part in chunker.split_text(cleaned, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP):
                pieces.append((page_number, part))
        if not pieces:
            raise EmptyPDFError()

        vectors = embeddings.embed_texts([text for _, text in pieces])
        model_name = settings.EMBEDDING_MODEL_NAME

        objs = []
        for index, ((page_number, text), vector) in enumerate(zip(pieces, vectors)):
            chunk = DocumentChunk(document=document, chunk_index=index, page_number=page_number,
                                  text=text, embedding_model=model_name)
            chunk.set_embedding(vector)
            objs.append(chunk)
        with transaction.atomic():
            document.chunks.all().delete()
            DocumentChunk.objects.bulk_create(objs)

        ids = list(document.chunks.order_by("chunk_index").values_list("id", flat=True))
        vector_store.add_vectors(ids, vectors)

        suspicious = sum(1 for _, text in pieces if prompts.looks_like_injection(text))
        document.page_count = len(pages)
        document.chunk_count = len(pieces)
        document.status = Document.Status.READY
        document.error_message = (
            f"Warning: {suspicious} passage(s) look like instructions to an AI system. "
            "They will be ignored when answering questions." if suspicious else ""
        )
        document.save()
    except RAGError as exc:
        _mark_failed(document, exc.user_message)
    except Exception:
        logger.exception("Unexpected error processing document %s", document.pk)
        _mark_failed(document, "An unexpected error occurred while processing this file. See the server log.")
    return document


def rebuild_index():
    """Rebuild the FAISS index from the database (source of truth). Returns number of vectors."""
    ready = DocumentChunk.objects.filter(document__status=Document.Status.READY)
    if ready.exclude(embedding_model=settings.EMBEDDING_MODEL_NAME).exists():
        raise VectorStoreError(
            "Some documents were embedded with a different model than EMBEDDING_MODEL_NAME. "
            "Delete and re-upload those documents."
        )
    import numpy as np
    ids, vectors = [], []
    for chunk in ready.order_by("id").iterator():
        ids.append(chunk.id)
        vectors.append(chunk.get_embedding())
    vector_store.replace_all(ids, np.vstack(vectors) if vectors else None)
    return len(ids)


def delete_document(document):
    """Delete the row (chunks cascade, PDF file removed), then rebuild the index safely."""
    document.delete()
    return rebuild_index()
