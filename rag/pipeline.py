"""The whole RAG flow in one function: answer_question()."""
import logging
import re
from dataclasses import dataclass, field

from . import llm_client, prompts, retriever, vector_store
from .exceptions import RAGError

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    answer: str
    sources: list = field(default_factory=list)
    answer_found: bool = True
    is_error: bool = False


def _not_found():
    return RAGResult(prompts.NOT_FOUND_MESSAGE, [], answer_found=False)


def answer_question(question, user, history=None):
    """history: list of {"role": "user"|"assistant", "content": str}, oldest first."""
    history = history or []
    try:
        if vector_store.size() == 0:
            return RAGResult(prompts.NO_DOCUMENTS_MESSAGE, [], answer_found=False)

        queries = [question]
        last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), None)
        if last_user:   # helps follow-ups like "what about sick leave?"
            queries.append(f"{last_user} {question}")

        chunks = retriever.retrieve(queries, user)

        safe = []
        for chunk in chunks:
            if prompts.looks_like_injection(chunk.text):
                logger.warning("Excluded suspicious chunk %s from %s", chunk.chunk_id, chunk.filename)
                continue
            safe.append(chunk)
        if not safe:
            return _not_found()   # nothing relevant: the LLM is NOT called

        messages = prompts.build_messages(question, safe, history)
        raw = llm_client.generate(messages)

        if prompts.NOT_FOUND_TOKEN in raw:
            leftover = raw.replace(prompts.NOT_FOUND_TOKEN, "").strip(" .\n\t")
            if not leftover:
                return _not_found()
            raw = leftover

        refs = {int(n) for n in re.findall(r"\[(\d{1,2})\]", raw)}
        used = [(i, c) for i, c in enumerate(safe, start=1) if i in refs] or list(enumerate(safe, start=1))
        sources = [
            {"ref": i, "document": c.filename, "title": c.title, "page": c.page,
             "chunk_id": c.chunk_id, "score": round(c.score, 3)}
            for i, c in used
        ]
        return RAGResult(raw, sources, answer_found=True)

    except RAGError as exc:
        logger.warning("RAG error: %s", exc.user_message)
        return RAGResult(exc.user_message, [], answer_found=False, is_error=True)
    except Exception:
        logger.exception("Unexpected error while answering")
        return RAGResult("Something unexpected went wrong. Please try again or contact the administrator.",
                         [], answer_found=False, is_error=True)
