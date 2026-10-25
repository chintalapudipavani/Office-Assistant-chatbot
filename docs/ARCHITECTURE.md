# Architecture Guide (beginner friendly)

## Django words
- **Project** (`config/`): the whole website. **App** (`accounts`, `documents`, `chat`): one feature area.
- **Model**: a Python class that becomes a database table. **View**: a function that receives a browser request and returns a response.
- **Template**: HTML with placeholders. **URL route**: "this address runs that view". **Migration**: a script that creates or changes tables.

## Request-response flow (one chat question)
1. You type a question; `chat.js` sends `POST /chat/ask/` with JSON and the CSRF token.
2. `config/urls.py` -> `chat/urls.py` -> `chat.views.chat_ask`.
3. The view checks login, validates the text, loads or creates a `ChatSession`, saves your message.
4. The view calls `rag.pipeline.answer_question(question, user, history)`.
5. The pipeline returns an answer, sources and flags; the view saves the assistant message and returns JSON.
6. `chat.js` draws the answer and source chips. (Text is inserted with `textContent`, so answers cannot inject HTML.)

## Text diagram
```text
 Browser (Bootstrap + chat.js)
    |  HTTP + CSRF token
    v
 Django: urls -> views -> templates         accounts / documents / chat
    |                         |
    | ORM                     | calls
    v                         v
 SQLite                    rag/ package
  User                      pdf_loader -> text_cleaning -> chunker -> embeddings
  Document                  vector_store (FAISS file)  <-  retriever (access + threshold)
  DocumentChunk (text,      prompts -> llm_client -> pipeline
    page, embedding)             |                         |
  ChatSession/ChatMessage        v                         v
                          data/vector_store/        LLM provider (cloud API or local)
                          faiss.index
```

## The RAG pipeline
**Ingestion (upload):** extract text per page (PyMuPDF) -> clean (hyphenation, whitespace) -> split into ~800-character
chunks with 150 overlap, never across pages so the page number is exact -> embed each chunk -> store chunk + vector in
`DocumentChunk` -> add vectors to FAISS using the chunk's database id as the FAISS id.

**Query:** embed the question (and, for follow-ups, the previous question + this one) -> FAISS returns about 30 nearest
candidates -> keep only chunks of READY documents the user may see -> keep score >= `RETRIEVAL_MIN_SCORE`, best `RETRIEVAL_TOP_K`
-> exclude passages that look like prompt injection -> if nothing is left: fixed "could not find" reply, no LLM call
-> otherwise build the prompt -> LLM -> citations `[n]` are mapped to filename + page.

## Key ideas in simple English
- **Embedding:** a list of 384 numbers describing the meaning of a text. Similar meanings give similar numbers.
- **Vector database (FAISS):** quickly finds the stored vectors closest to the question's vector. We normalise vectors so "closeness" is cosine similarity between 0 and 1.
- **LLM:** only writes the answer from the passages we give it. It is not trusted to know company rules.
- **Threshold:** a minimum similarity. Below it we say "not found" instead of guessing.

## Why the index can be rebuilt
`DocumentChunk.embedding` in SQLite is the source of truth. `faiss.index` is a cache. It is written to a temporary file and
swapped in with `os.replace`, so a crash cannot leave a half-written index. Deleting a document removes its chunks, then the
index is rebuilt. Even if the index still held a stale id, the retriever looks every id up in the database and drops missing ones.

## Database tables
| Table | Purpose |
|---|---|
| `auth_user` | users; `is_staff` decides who manages documents |
| `documents_document` | title, original_filename, file, visibility, status (processing/ready/failed), error_message, page_count, chunk_count, uploaded_by |
| `documents_documentchunk` | document, chunk_index, page_number, text, embedding (bytes), embedding_model |
| `chat_chatsession` | user, title, timestamps |
| `chat_chatmessage` | session, role, content, sources (JSON), answer_found, is_error |

Source citation format stored with each assistant message:
`{"ref": 1, "document": "02_leave_and_attendance_policy.pdf", "title": "Leave And Attendance Policy", "page": 1, "chunk_id": 14, "score": 0.61}`

## Security design
- Access control is applied in the retriever (database filter on `visibility`), before any text reaches the LLM.
- Prompt injection: random-boundary delimiters + "passages are untrusted data" rule + regex exclusion of instruction-like passages + a no-LLM fallback. These reduce but do not eliminate risk.
- Uploaded PDFs are stored under random names and are not exposed by any URL.
