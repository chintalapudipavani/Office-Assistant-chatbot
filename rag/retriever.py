"""Search the index, enforce access control, apply the relevance threshold."""
from dataclasses import dataclass

from django.conf import settings

from documents.models import Document, DocumentChunk

from . import embeddings, vector_store


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    title: str
    filename: str
    page: int
    text: str
    score: float


def retrieve(queries, user, top_k=None, min_score=None):
    """queries: list of strings (the question, optionally plus a follow-up-expanded version).
    Returns the best chunks the USER IS ALLOWED TO SEE, above the similarity threshold."""
    top_k = top_k or settings.RETRIEVAL_TOP_K
    min_score = settings.RETRIEVAL_MIN_SCORE if min_score is None else min_score
    # Ask FAISS for extra candidates because some may be filtered out for this user.
    candidate_k = max(top_k * 6, 30)

    best = {}   # chunk_id -> best score across all queries
    for query in queries:
        vector = embeddings.embed_query(query)
        for chunk_id, score in vector_store.search(vector, candidate_k):
            if score > best.get(chunk_id, -1.0):
                best[chunk_id] = score
    if not best:
        return []

    qs = DocumentChunk.objects.filter(id__in=best.keys(), document__status=Document.Status.READY)
    if not getattr(user, "is_staff", False):
        qs = qs.filter(document__visibility=Document.Visibility.ALL)
    by_id = {c.id: c for c in qs.select_related("document")}

    results = []
    for chunk_id, score in sorted(best.items(), key=lambda kv: kv[1], reverse=True):
        chunk = by_id.get(chunk_id)
        if chunk is None or score < min_score:
            continue
        results.append(RetrievedChunk(
            chunk_id=chunk.id, document_id=chunk.document_id, title=chunk.document.title,
            filename=chunk.document.original_filename, page=chunk.page_number,
            text=chunk.text, score=score,
        ))
        if len(results) >= top_k:
            break
    return results
