# AI Knowledge Inbox

A minimal full-stack app to save notes and URLs, then ask questions over them using a RAG pipeline.

**Stack:** React · FastAPI · SQLAlchemy · FAISS · HuggingFace embeddings · LangGraph · Groq (`openai/gpt-oss-20b`)

---

## Features

- **Content ingestion:** save plain-text notes; any URL inside a note is fetched server-side, cleaned, and stored alongside the note.
- **Semantic search + RAG:** questions are embedded, the most relevant notes are retrieved from a FAISS vector store, and an LLM answers using that context.
- **Frontend:** React (hooks) UI to add, list, edit and delete notes, and to ask questions and read the answer.

---

## Architecture

```
React  ──HTTP──▶  FastAPI
                    │
                    ├─ SQLAlchemy ──▶ SQL database (notes)
                    ├─ url_reader.py ──▶ httpx + BeautifulSoup
                    └─ LangGraph pipeline
                          ragNode  (embed → FAISS → top-k)
                             │
                          llmNode  (context + question → LLM)
```

```
api/
  main.py            # FastAPI app, DB model, LangGraph pipeline, routes
  url_reader.py      # URL validation (SSRF guard) + content extraction
client/myapp/
  src/App.jsx        # Note form, note list, ask-a-question UI
```

### RAG pipeline

1. **Retrieve:** every note is a `Document` (`Title + Description`), embedded with `sentence-transformers/paraphrase-MiniLM-L3-v2` and indexed in FAISS. The top `k = min(3, n_notes)` matches are returned.
2. **Generate:** retrieved context and the question are sent to `openai/gpt-oss-20b` on Groq (`temperature=0`) and the answer is returned.
3. With no saved notes, the API responds immediately without calling the LLM.

### URL ingestion

- URLs are detected in the note text and fetched with async `httpx` (30s timeout, max 5 redirects).
- **SSRF protection:** hostnames are resolved and non-public IPs (private, loopback, link-local) are rejected; URLs with embedded credentials are rejected.
- Only `text/html` is accepted. Boilerplate tags (`script`, `style`, `nav`, `footer`, `header`, `noscript`, `iframe`, `svg`) are stripped, whitespace is normalised, and content is capped at 15,000 characters.
- If a page can't be fetched, the note is still saved as written.

---

## API

Base URL: `http://localhost:8000` · Interactive docs: `/docs`

| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/notes` | `{ "title", "description" }` | Ingest a note (fetches any URLs inside it) |
| `GET` | `/notes` | none | List notes, newest first |
| `GET` | `/notes/{id}` | none | Get one note |
| `PUT` | `/notes/{id}` | `{ "title", "description" }` | Update a note |
| `DELETE` | `/notes/{id}` | none | Delete a note |
| `POST` | `/askragai` | `{ "qst" }` | Ask a question, returns `{ "question", "answer" }` |

**Validation & status codes:** `200` success · `400` empty title / description / question · `404` note not found · `500` database or AI failure, with a readable message in `detail`.

---

## Run locally

**Prerequisites:** Python 3.10+, Node 18+, a [Groq API key](https://console.groq.com), and a SQLAlchemy database URL (PostgreSQL or SQLite).

### Backend

```bash
cd api
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `api/.env`:

```env
database_url=postgresql://user:password@localhost:5432/notesdb
# or: database_url=sqlite:///./notes.db
GROQ_API_KEY=your_groq_key
```

```bash
uvicorn main:app --reload --port 8000
```

The table is created automatically on startup.

### Frontend

```bash
cd client/myapp
npm install
npm start        # http://localhost:3000
```

---

## Design decisions & tradeoffs

**Chunking:** one note is one retrievable unit (title + body). Notes are short, so keeping them whole preserves context and keeps retrieval simple and predictable.

**Embeddings:** a local `MiniLM` model, so there are no API costs or keys for embedding and it runs fast on CPU.

**Vector store:** in-memory FAISS. It needs no extra infrastructure and is a good fit for a single-user knowledge base. SQL remains the durable source of truth.

**Orchestration:** LangGraph models the pipeline as explicit nodes (`ragNode` → `llmNode`), so steps like reranking or query rewriting can be added without restructuring.

**Separation of concerns:** URL fetching/validation lives in its own module; the database model, retrieval, generation and routes are separate units within the API.

### What changes at scale

- Embeddings computed at ingest and persisted, instead of at query time.
- Long content split into overlapping chunks (about 500 tokens) with note-id references.
- A persistent vector index (pgvector, or a persisted FAISS/Chroma index) updated incrementally.
- URL fetching and embedding moved to a background worker queue.
- Pagination on listing endpoints.

### Production roadmap

- Return source snippets with each answer for traceability.
- Structured JSON logging with request IDs.
- Timeouts and retries around the LLM call.
- Rate limiting, request-size limits, and environment-driven CORS/API URLs.
- Migrations (Alembic), automated tests, and Docker Compose.
