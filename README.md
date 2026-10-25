# AI-Powered Intelligent Office Assistant (Django + RAG + LLM)

A web chatbot that answers employee questions **only from uploaded office PDFs** and shows the
document name and page for each answer. If the documents do not contain the answer, it says so.

> All sample documents are **fictional** (company: "Brightwave Solutions"). They are not real policies.

## 1. Features
- Home page, registration, login, logout (Django authentication, CSRF protection)
- Chat page with natural-language questions, follow-up questions, source citations (file + page)
- Chat history saved in the database (view and delete your own conversations)
- Staff-only document management: upload PDF, list, delete, rebuild search index
- Per-document visibility: **All employees** or **Staff only** (staff-only text is never sent to the LLM for ordinary users)
- PDF text extraction (PyMuPDF) -> cleaning -> chunking -> embeddings (Sentence Transformers) -> FAISS index
- Configurable LLM through `.env` (any OpenAI-compatible API, including a local Ollama server)
- Safe fallback when nothing relevant is found (the LLM is not even called)
- Prompt-injection defences, clear error messages, 21 automated tests, a retrieval/faithfulness evaluation script

## 2. Technology and versions
| Part | Choice |
|---|---|
| Python | 3.10 to 3.13 (3.12 recommended) |
| Web | Django 5.2 LTS, Bootstrap 5.3 (CDN), vanilla JavaScript |
| Database | SQLite |
| PDF | PyMuPDF >= 1.24.3 |
| Embeddings | `sentence-transformers` with `all-MiniLM-L6-v2` (384 dimensions, runs locally) |
| Vector store | `faiss-cpu` |
| LLM | `openai` SDK pointed at any OpenAI-compatible endpoint |
| RAG framework | none (plain Python, so you can read and explain every step) |

Version ranges are in `requirements.txt`. After a successful install run
`pip freeze > requirements.lock.txt` to record the exact versions that worked for you.

## 3. Folder structure
```text
office_assistant_project/
  manage.py                  Django command tool
  requirements.txt           packages to install
  .env.example               settings template (copy to .env)
  .gitignore                 keeps .env, db, uploads and the index out of Git
  config/                    Django project: settings.py (all settings), urls.py (address book)
  accounts/                  register / login / logout
  documents/                 models (Document, DocumentChunk), upload form, views, services.py (ingestion),
                             permissions.py, management/commands/ (rebuild_index, ingest_samples), tests.py
  chat/                      models (ChatSession, ChatMessage), views (home, chat, ask, history), tests.py
  rag/                       the RAG engine (no Django views here)
    pdf_loader.py            PDF -> text per page
    text_cleaning.py         tidy the text
    chunker.py               split into overlapping chunks
    embeddings.py            text -> vectors
    vector_store.py          FAISS index (atomic save, reload when the file changes)
    retriever.py             search + access control + relevance threshold
    prompts.py               system prompt, untrusted-context delimiters, injection scan
    llm_client.py            calls the LLM, converts failures into friendly errors
    pipeline.py              answer_question(): the whole flow
    exceptions.py            custom errors with user-safe messages
    testing.py               fake embedder used only by automated tests
  templates/                 HTML pages (base, home, chat, history, documents, login, register, 403)
  static/css/style.css       styling
  static/js/chat.js          sends questions, renders answers and sources
  sample_documents/          7 fictional .txt files + generated PDFs, and optional/ (prompt-injection test)
  tools/make_sample_pdfs.py  converts the .txt samples to PDFs
  evaluation/                test_questions.json + evaluate.py
  docs/                      ARCHITECTURE.md, TEST_CASES.md
  media/documents/           uploaded PDFs (git-ignored, never served by a URL)
  data/vector_store/         faiss.index (git-ignored, rebuildable)
```

## 4. Installation on Windows (Anaconda Prompt)
Open **Anaconda Prompt**. Commands marked ONCE are run one time. Commands marked EVERY TIME are run each time you work.

```bat
:: ONCE - unzip the project, then go into it (adjust the path)
cd %USERPROFILE%\Documents\office_assistant_project

:: ONCE - create a private Python environment
conda create -n officeai python=3.12 -y

:: EVERY TIME you open a new Anaconda Prompt
conda activate officeai

:: ONCE - install packages (PyTorch CPU first; large download)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

:: ONCE - check the install
python -c "import django, pymupdf, faiss, numpy, openai, sentence_transformers; print('All imports OK', django.get_version())"

:: ONCE - settings file
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(50))"
```
Paste the printed key after `DJANGO_SECRET_KEY=` in `.env` (no quotes). Then configure the LLM (section 5).

```bat
:: ONCE (and again after any model change) - create the database tables
python manage.py migrate

:: ONCE - create your admin login
python manage.py createsuperuser

:: ONCE - sample PDFs are already included; run only if you edit the .txt files
python tools\make_sample_pdfs.py

:: ONCE - load the sample documents and build the index (first run downloads the ~90 MB embedding model)
python manage.py ingest_samples

:: EVERY TIME - start the website, keep this window open
python manage.py runserver
```
Open **http://127.0.0.1:8000/** and log in at **http://127.0.0.1:8000/accounts/login/**.
Stop the server with `Ctrl + C`. Django's `runserver` is for local development only, never for real deployment.

Plain Command Prompt works too: replace the conda lines with `python -m venv venv` and `venv\Scripts\activate.bat`.

## 5. Configure the LLM (`.env`)
After editing `.env`, stop and restart the server.

| Provider | Settings |
|---|---|
| OpenAI | `LLM_API_KEY=your key`, `LLM_BASE_URL=` (empty), `LLM_MODEL=gpt-4o-mini` |
| Groq | `LLM_BASE_URL=https://api.groq.com/openai/v1`, your key, a current model name from Groq |
| OpenRouter | `LLM_BASE_URL=https://openrouter.ai/api/v1`, your key, a model name |
| Local Ollama | install Ollama, `ollama pull llama3.2`, then `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_API_KEY=ollama`, `LLM_MODEL=llama3.2` |

Model names change over time; use a name your provider currently lists. Never share or commit `.env`.

## 6. Using the app
1. Log in as the superuser (superusers are staff, so they can manage documents).
2. **Documents** page: upload PDFs, delete them, or click **Rebuild index**.
3. Register a normal account (second browser or private window). Normal users can chat but get "403" on `/documents/`.
4. To make someone a document manager: `/admin/` -> Users -> choose the user -> tick **Staff status** -> Save.
5. Ask questions in **Chat**. Each answer lists sources like `[1] 02_leave_and_attendance_policy.pdf, page 1`.
6. Test the access control: `07_confidential_salary_bands.pdf` is loaded as **Staff only**. Ask "What is the annual salary band for a Software Engineer?" as staff (answer found) and as a normal user (not found).
7. Optional injection test: `python manage.py ingest_samples --folder sample_documents\optional`, then see `docs/TEST_CASES.md`.

## 7. How the RAG pipeline works (short version)
Upload: PDF -> text per page -> clean -> chunks (about 800 characters, 150 overlap, never crossing a page) ->
384-number vectors -> saved in SQLite (source of truth) and added to the FAISS file.
Question: embed the question -> FAISS finds the nearest chunks -> drop chunks the user may not see ->
drop chunks below `RETRIEVAL_MIN_SCORE` -> if none left, reply "could not find" without calling the LLM ->
otherwise send the chunks to the LLM inside delimiters, as untrusted data -> answer with `[1]`-style citations -> save.
Delete a document: rows and the PDF file are removed, then the index is rebuilt from the database and swapped in atomically.
Details: `docs/ARCHITECTURE.md`.

## 8. Security, privacy and reliability
- Django authentication and CSRF protection; document pages need staff status; users only see their own chats.
- Uploads: `.pdf` extension, `%PDF-` header check, empty-file check, size limit (`MAX_UPLOAD_SIZE_MB`), random stored file name, no public URL for uploaded files.
- Secrets only in `.env`; `.env` is git-ignored.
- Prompt injection: retrieved text is wrapped in random-boundary delimiters and declared untrusted in the system prompt;
  passages that look like instructions to an AI are excluded. This reduces the risk; it cannot guarantee safety.
- **Privacy:** with a cloud LLM, the question, recent chat history and the retrieved passages are sent to that provider.
  Embeddings are computed locally. Do not upload documents your organisation does not allow to leave its network;
  check the provider's data-retention terms, or use a local model (Ollama) for sensitive material.
  Administrators can read all chats in `/admin/`; inform users and delete old chats according to your policy.
- The system does **not** guarantee correct answers. Always verify important details with HR.

## 9. Limitations
- Scanned PDFs (images) are rejected: there is no OCR. Tables can extract poorly.
- Upload processing is synchronous, so large PDFs make the browser wait.
- FAISS flat index and SQLite suit hundreds to tens of thousands of chunks, not millions.
- Retrieval threshold needs tuning for your documents; the follow-up handling is simple.
- Embedding vectors are stored in SQLite and the index file is cached in memory per process.

## 10. Future enhancements
OCR for scanned PDFs, background processing (Celery), `.docx`/`.txt` upload, streaming answers,
re-ranking, hybrid keyword + vector search, per-department access groups, answer feedback buttons,
PostgreSQL + pgvector, HTTPS deployment with gunicorn/nginx.

## 11. Troubleshooting
| Problem | What to do |
|---|---|
| `'python' is not recognized` | Use Anaconda Prompt, or `py` instead of `python`. |
| `ModuleNotFoundError` | The environment is not active. Run `conda activate officeai`, then `pip install -r requirements.txt`. |
| PyTorch error about a missing DLL | Install the Microsoft Visual C++ Redistributable (x64), then retry. |
| `OMP: Error #15` | Already worked around in `settings.py`. If it still appears, run `set KMP_DUPLICATE_LIB_OK=TRUE` first. |
| Embedding model download fails | The first run needs internet (huggingface.co). Check proxy/firewall, then retry `ingest_samples`. |
| Chat says "LLM is not configured" | Set `LLM_API_KEY` in `.env` and restart the server. |
| Chat says the key was rejected / model not found | Check the key, `LLM_MODEL` and `LLM_BASE_URL` for your provider. |
| Document status "Failed: No readable text" | The PDF is a scan. Use a text-based PDF. |
| Everything answers "could not find" | Check Documents shows Ready; lower `RETRIEVAL_MIN_SCORE` (for example 0.25); click Rebuild index. |
| Wrong answers get through | Raise `RETRIEVAL_MIN_SCORE` (for example 0.35) and re-run `evaluate.py`. |
| `no such table` | Run `python manage.py migrate`. |
| Port 8000 busy | `python manage.py runserver 8001`. |
| Settings changes ignored | Stop (`Ctrl + C`) and restart the server. |
| Page looks unstyled | Bootstrap loads from a CDN; you need internet access. |
| `403 Forbidden` on /documents/ | Your account is not staff. Tick Staff status in `/admin/`. |
| Index and database disagree | Documents page -> Rebuild index, or `python manage.py rebuild_index`. |

## 12. Testing
```bat
python manage.py test                          :: 21 automated tests (fake embedder, mocked LLM; no downloads, no API cost)
python evaluation\evaluate.py --retrieval-only :: retrieval quality with the REAL embedding model (no LLM cost)
python evaluation\evaluate.py                  :: adds LLM answers and a faithfulness check
```
Manual test cases: `docs/TEST_CASES.md`.
"# Office_Assistant" 
