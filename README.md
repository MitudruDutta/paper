# Paper

A multimodal document processing system with AI capabilities. Paper provides a robust backend for uploading, validating, and managing PDF documents with plans for future AI-powered extraction and analysis features.

## Overview

Paper is built as a phased project where each phase adds new capabilities while maintaining stability:

- **Phase 0 (Complete)**: Infrastructure foundation with FastAPI, Supabase PostgreSQL, Redis, and Qdrant
- **Phase 1 (Complete)**: Document ingestion, validation, and persistent storage
- **Phase 2 (Complete)**: Text extraction from native and scanned PDFs with OCR
- **Phase 3 (Complete)**: Semantic chunking and vector indexing for retrieval
- **Phase 4 (Complete)**: RAG-based question answering with citations
- **Phase 5 (Complete)**: Multi-document QA, follow-up questions, and confidence scoring

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend Framework** | Python 3.11, FastAPI, Uvicorn | Async REST API with automatic OpenAPI docs |
| **Database** | Supabase PostgreSQL | Document metadata storage with SSL encryption |
| **ORM** | SQLAlchemy 2.x (async) + asyncpg | Async database operations |
| **Cache** | Redis 7 | Session management and future caching needs |
| **Vector Database** | Qdrant | Future semantic search capabilities |
| **Validation** | Pydantic v2, PyMuPDF | Request/response validation and PDF integrity checks |
| **OCR** | Tesseract, pdf2image, Pillow | Text extraction from scanned documents |
| **Containerization** | Docker + Docker Compose v2 | Consistent development and deployment |

## Prerequisites

Before you begin, ensure you have:

1. **Docker and Docker Compose v2** installed on your system
2. **Supabase account** with a PostgreSQL database project
   - Sign up at [supabase.com](https://supabase.com)
   - Create a new project and note your database credentials
   - Enable the `pgcrypto` extension: `CREATE EXTENSION IF NOT EXISTS "pgcrypto";`

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/MitudruDutta/paper.git
cd paper
```

### 2. Configure Environment Variables

Copy the example environment file and edit it with your credentials:

```bash
cp .env.example .env
```

Open `.env` and configure the following variables:

#### Required: Supabase Database Connection

```bash
# Get these from your Supabase project dashboard → Settings → Database
SUPABASE_DB_HOST=your-project-ref.supabase.co
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your_database_password
SUPABASE_DB_SSL=true
```

To find your Supabase credentials:
1. Go to your Supabase project dashboard
2. Click "Connect" button (top right)
3. Select "Direct Connection" or "Session pooler"
4. Extract host, port, and password from the connection string

#### Optional: Service Configuration

```bash
# Redis (defaults work for Docker setup)
REDIS_HOST=redis
REDIS_PORT=6379

# Qdrant (defaults work for Docker setup)
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# API
API_PORT=8000

# Document Storage
DOCUMENT_STORAGE_PATH=/data/documents  # Must be absolute path
MAX_UPLOAD_SIZE_MB=50                   # 1-5000 MB allowed
```

### 3. Start the Application

```bash
# Build and start all services
docker-compose -f infrastructure/docker-compose.yml up --build

# Or run in detached mode (background)
docker-compose -f infrastructure/docker-compose.yml up --build -d
```

### 4. Verify Installation

Check that all services are healthy:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "services": {
    "database": "connected",
    "redis": "connected",
    "qdrant": "connected"
  },
  "startup_issues": []
}
```

## Usage

### API Documentation

Once running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Uploading Documents

Upload a PDF document using curl or any HTTP client:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@/path/to/your/document.pdf"
```

**Success Response (HTTP 200):**

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "status": "validated"
}
```

**Error Response (HTTP 422 - Invalid PDF):**

```json
{
  "detail": "Invalid PDF file: Password-protected PDFs are not supported"
}
```

#### Upload Validation Rules

The upload endpoint enforces these rules:

| Rule | Behavior |
|------|----------|
| File type | Only `application/pdf` MIME type accepted |
| File size | Maximum 50 MB (configurable via `MAX_UPLOAD_SIZE_MB`) |
| PDF integrity | Corrupted files are rejected |
| Password protection | Encrypted PDFs are rejected |
| Empty files | Zero-byte files are rejected |

### Listing Documents

Retrieve all uploaded documents, ordered by creation date (newest first):

```bash
curl http://localhost:8000/documents
```

**Response:**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "report.pdf",
    "status": "validated",
    "file_size": 1048576,
    "created_at": "2024-01-15T10:30:00Z"
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "filename": "invoice.pdf",
    "status": "failed",
    "file_size": 524288,
    "created_at": "2024-01-14T09:15:00Z"
  }
]
```

### Getting Document Details

Retrieve full metadata for a specific document:

```bash
curl http://localhost:8000/documents/550e8400-e29b-41d4-a716-446655440000
```

**Response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "report.pdf",
  "stored_filename": "550e8400-e29b-41d4-a716-446655440000.pdf",
  "file_size": 1048576,
  "mime_type": "application/pdf",
  "page_count": 10,
  "status": "validated",
  "error_message": null,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Not Found Response (HTTP 404):**

```json
{
  "detail": "Document not found: no document with ID 550e8400-e29b-41d4-a716-446655440000"
}
```

## Document Lifecycle

Documents progress through a simple state machine:

```
┌──────────┐     ┌───────────┐
│  Upload  │────▶│ Validated │  (PDF is valid, stored successfully)
└──────────┘     └───────────┘
      │
      │          ┌──────────┐
      └─────────▶│  Failed  │  (Invalid, corrupted, or password-protected)
                 └──────────┘
```

| Status | Description |
|--------|-------------|
| `uploaded` | Initial state during processing (transient) |
| `validated` | PDF passed all checks and is stored permanently |
| `failed` | PDF rejected; `error_message` field contains the reason |

## File Storage

### How It Works

1. **Upload**: Files are first saved to a temporary directory
2. **Validation**: PyMuPDF validates PDF integrity and extracts page count
3. **Storage**: Valid files are moved to permanent storage with UUID-based filenames
4. **Cleanup**: Temporary files and partial uploads are automatically cleaned up

### Storage Location

- **Container path**: `/data/documents`
- **Docker volume**: `document_data` (persists across container restarts)
- **Filename format**: `{document_id}.pdf` (e.g., `550e8400-e29b-41d4-a716-446655440000.pdf`)

### Security Features

- Path traversal protection on all file operations
- UUID-based filenames prevent conflicts and enumeration
- File paths are never exposed in API responses
- Extension whitelist validation (alphanumeric only)

## Phase 2: Text Extraction

Phase 2 adds the ability to extract text from PDF documents, handling both native (text-based) and scanned (image-based) PDFs.

### How It Works

1. **Page Classification**: Each page is analyzed independently to determine if it contains native text or is a scanned image
2. **Native Extraction**: Pages with embedded text (>50 characters) are extracted using PyMuPDF
3. **OCR Pipeline**: Scanned pages are converted to images and processed with Tesseract OCR
4. **Storage**: Extracted text is stored per-page in the `document_pages` table

### Native vs Scanned PDFs

| Type | Detection | Extraction Method | Confidence |
|------|-----------|-------------------|------------|
| **Native** | Text length ≥ 50 chars | PyMuPDF `get_text()` | 1.0 (perfect) |
| **Scanned** | Text length < 50 chars | Tesseract OCR | 0.0-1.0 (varies) |

### Triggering Extraction

```bash
# Async extraction (recommended for large documents)
curl -X POST http://localhost:8000/documents/{id}/extract-text

# Synchronous extraction (blocks until complete)
curl -X POST "http://localhost:8000/documents/{id}/extract-text?sync=true"
```

**Response:**
```json
{
  "document_id": "uuid",
  "total_pages": 12,
  "native_pages": 8,
  "scanned_pages": 4,
  "skipped_pages": 0,
  "failed_pages": 0,
  "status": "completed"
}
```

### Checking Extraction Status

```bash
curl http://localhost:8000/documents/{id}/extraction-status
```

### Retrieving Extracted Text

```bash
# List all pages
curl http://localhost:8000/documents/{id}/pages

# Get specific page text
curl http://localhost:8000/documents/{id}/pages/0
```

### Where Text Is Stored

Extracted text is stored in the `document_pages` table:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `document_id` | UUID | Reference to parent document |
| `page_number` | INTEGER | 0-indexed page number |
| `page_type` | TEXT | `native` or `scanned` |
| `extracted_text` | TEXT | The extracted text content |
| `confidence` | REAL | OCR confidence (1.0 for native) |
| `created_at` | TIMESTAMPTZ | Extraction timestamp |

### Known Limitations

- OCR results with confidence < 0.6 are discarded
- Complex layouts may not preserve exact reading order
- Tables and charts are not specially handled
- Handwritten text has low OCR accuracy
- Re-extraction skips existing pages (delete pages to re-extract)

## Phase 3: Semantic Chunking & Vector Search

Phase 3 transforms extracted text into searchable knowledge through semantic chunking and vector embeddings.

### How It Works

1. **Chunking**: Document text is split into semantic chunks (500-800 tokens) with overlap
2. **Embedding**: Each chunk is converted to a 768-dimensional vector using `nomic-embed-text`
3. **Storage**: Vectors stored in Qdrant, metadata in PostgreSQL
4. **Search**: Query text is embedded and matched against stored vectors using cosine similarity

### Why Chunking?

- LLMs have context limits - chunks fit within those limits
- Semantic chunks preserve meaning better than arbitrary splits
- Overlap ensures context isn't lost at boundaries
- Page tracking enables source attribution

### Triggering Indexing

```bash
# Async indexing (recommended)
curl -X POST http://localhost:8000/documents/{id}/index

# Synchronous indexing
curl -X POST "http://localhost:8000/documents/{id}/index?sync=true"
```

**Response:**
```json
{
  "document_id": "uuid",
  "chunks_created": 21,
  "status": "indexed"
}
```

### Semantic Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "top_k": 5}'
```

**Response:**
```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "content": "Relevant text...",
      "page_start": 12,
      "page_end": 13,
      "score": 0.85
    }
  ],
  "query": "your search query"
}
```

### Where Chunks Are Stored

Chunk metadata is stored in the `document_chunks` table:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (also used as Qdrant point ID) |
| `document_id` | UUID | Reference to parent document |
| `page_start` | INTEGER | First page of chunk |
| `page_end` | INTEGER | Last page of chunk |
| `chunk_index` | INTEGER | Sequential index within document |
| `content` | TEXT | The chunk text |
| `token_count` | INTEGER | Estimated token count |
| `embedding_id` | UUID | Reference to Qdrant vector |

### Prerequisites

- **Ollama** must be running with `nomic-embed-text` model:
  ```bash
  OLLAMA_HOST=0.0.0.0 ollama serve &
  ollama pull nomic-embed-text
  ```

### Known Limitations

- Requires Ollama running on host (not in Docker)
- Re-indexing deletes and recreates all chunks
- No reranking (raw cosine similarity scores)
- Tables and images are not specially handled

## Phase 4: Question Answering with Citations

Phase 4 transforms Paper from a retrieval system into a document question-answering system with verifiable citations.

### How It Works

1. **Question Input**: User asks a question about a specific document
2. **Retrieval**: System embeds the question and retrieves the top 5 most relevant chunks
3. **Context Assembly**: Retrieved chunks are formatted with page references
4. **LLM Generation**: Local LLM (Llama 3.1 8B) generates an answer using only the provided context
5. **Citation Validation**: All page citations in the answer are verified against retrieved chunks
6. **Response**: Answer is returned with source attribution

### Citation System

Every factual statement in an answer must include a citation in the format:
- `[Page X]` for single-page references
- `[Pages X-Y]` for multi-page references

Citations are validated against the actual retrieved chunks. If any citation references a page not in the retrieved context, the answer is regenerated.

### Hallucination Prevention

Paper prevents hallucinations through multiple mechanisms:

1. **Strict System Prompt**: The LLM is instructed to only use provided context
2. **Citation Requirement**: Every claim must be cited
3. **Citation Validation**: Invalid citations trigger regeneration
4. **Refusal Capability**: If information isn't found, the system explicitly says so
5. **No External Knowledge**: The LLM cannot use training data for answers

### Asking Questions

```bash
curl -X POST http://localhost:8000/documents/{document_id}/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the main topic of this document?"}'
```

**Success Response:**
```json
{
  "answer": "The document discusses machine learning deployment strategies [Page 5]. It covers CI/CD pipelines for ML models [Pages 12-14] and monitoring best practices [Page 20].",
  "sources": [
    {"page_start": 5, "page_end": 5, "chunk_id": "uuid"},
    {"page_start": 12, "page_end": 14, "chunk_id": "uuid"},
    {"page_start": 20, "page_end": 20, "chunk_id": "uuid"}
  ]
}
```

**Insufficient Context Response:**
```json
{
  "answer": "I cannot find this information in the provided document.",
  "sources": []
}
```

### LLM Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Primary Model | `llama3.1:8b` | Local Ollama model |
| Fallback Model | `gpt-4o-mini` | Used only if local fails |
| Temperature | 0.2 | Low for deterministic outputs |
| Max Tokens | 800 | Maximum answer length |

### Prerequisites

Ollama must be running with the Llama 3.1 model:
```bash
OLLAMA_HOST=0.0.0.0 ollama serve &
ollama pull llama3.1:8b
```

### Known Limitations

- Single document queries only (no cross-document synthesis)
- No conversation memory (each question is independent)
- No streaming responses
- Tables and charts are not specially handled
- Maximum question length: 500 characters

## API Reference

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API information and version |
| `GET` | `/health` | Health check for all services |
| `POST` | `/documents/upload` | Upload a PDF document |
| `GET` | `/documents` | List all documents |
| `GET` | `/documents/{id}` | Get document details by ID |
| `POST` | `/documents/{id}/extract-text` | Trigger text extraction |
| `GET` | `/documents/{id}/extraction-status` | Get extraction status |
| `GET` | `/documents/{id}/pages` | List extracted pages |
| `GET` | `/documents/{id}/pages/{page}` | Get extracted text for a page |
| `POST` | `/documents/{id}/index` | Trigger chunking and indexing |
| `POST` | `/search` | Semantic search across documents |
| `POST` | `/documents/{id}/ask` | Ask a question about a document |

### Health Check Response Codes

| Code | Status | Meaning |
|------|--------|---------|
| 200 | `ok` | All services healthy |
| 503 | `degraded` | One or more services unreachable |

## External Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8000 | Main application endpoint |
| Swagger Docs | http://localhost:8000/docs | Interactive API documentation |
| ReDoc | http://localhost:8000/redoc | Alternative API documentation |
| Qdrant Dashboard | http://localhost:6333/dashboard | Vector database management UI |

## Managing the Application

### View Logs

```bash
# All services
docker-compose -f infrastructure/docker-compose.yml logs -f

# Backend only
docker-compose -f infrastructure/docker-compose.yml logs -f backend
```

### Stop Services

```bash
# Stop and remove containers (keeps volumes)
docker-compose -f infrastructure/docker-compose.yml down

# Stop and remove everything including volumes (DATA LOSS)
docker-compose -f infrastructure/docker-compose.yml down -v
```

### Rebuild After Code Changes

```bash
docker-compose -f infrastructure/docker-compose.yml up --build
```

## Project Structure

```
paper/
├── backend/
│   ├── api/
│   │   ├── main.py              # FastAPI app entry point, lifespan management
│   │   ├── dependencies.py      # Shared dependencies (Qdrant client, service guards)
│   │   └── routes/
│   │       ├── health.py        # Health check endpoint
│   │       └── documents.py     # Document upload, list, get endpoints
│   ├── core/
│   │   ├── config.py            # Pydantic settings with validation
│   │   ├── database.py          # SQLAlchemy async engine and session
│   │   ├── redis.py             # Redis connection management
│   │   └── storage.py           # File storage operations
│   ├── models/
│   │   └── document.py          # SQLAlchemy Document model
│   ├── schemas/
│   │   └── document.py          # Pydantic request/response schemas
│   ├── requirements.txt         # Python dependencies
│   └── Dockerfile               # Backend container definition
├── infrastructure/
│   └── docker-compose.yml       # Multi-service orchestration
├── .env.example                 # Environment variable template
├── .gitignore
└── README.md
```

## Troubleshooting

### Services Won't Start

**Symptom**: Backend exits immediately after starting

**Solution**: Check that your Supabase credentials are correct in `.env`. The backend fails fast if it cannot connect to required services.

```bash
# View startup logs
docker-compose -f infrastructure/docker-compose.yml logs backend
```

### Database Connection Failed

**Symptom**: Health check shows `"database": "unreachable"`

**Solutions**:
1. Verify `SUPABASE_DB_HOST` and `SUPABASE_DB_PASSWORD` in `.env`
2. Ensure your IP is allowed in Supabase dashboard (Settings → Database → Connection Pooling)
3. Check that `pgcrypto` extension is enabled

### Upload Fails with "Invalid file type"

**Symptom**: PDF upload returns 400 error

**Solution**: Ensure the file has correct MIME type. Some systems may not detect PDFs correctly:

```bash
# Check file type
file --mime-type document.pdf

# Force MIME type in curl
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@document.pdf;type=application/pdf"
```

### Files Not Persisting

**Symptom**: Documents disappear after container restart

**Solution**: Ensure you're not using `docker-compose down -v` which removes volumes. Check that the `document_data` volume exists:

```bash
docker volume ls | grep document_data
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Phase 5: Advanced QA

Phase 5 extends Paper from single-document QA to a document reasoning system with conversation memory, multi-document comparison, and confidence scoring.

### Features

1. **Follow-up Questions**: Understands implicit references in conversation
2. **Multi-Document QA**: Query across multiple documents with clear source attribution
3. **Confidence Scoring**: Quantified answer reliability (0.0-1.0)

### How Follow-ups Work

Paper maintains conversation context and resolves coreferences:

```
Q1: "What was the revenue in Q3?"
A1: "Revenue in Q3 was $100M [Page 5]."

Q2: "How does that compare to Q2?"
→ Resolved to: "How does Q3 revenue compare to Q2 revenue?"
```

The system:
- Extracts entities from previous exchanges (Q3, revenue, $100M)
- Detects references ("that", "it", "those")
- Rewrites the question to be standalone

### Multi-Document Queries

Query multiple documents simultaneously with clear source separation:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Compare revenue growth across both reports",
    "document_ids": ["uuid1", "uuid2"]
  }'
```

**Response Format:**
```json
{
  "answer": "Document: Annual_Report_2023.pdf:\n- Revenue grew 15% YoY [Page 12]\n\nDocument: Annual_Report_2024.pdf:\n- Revenue grew 9% YoY [Page 14]\n\nComparison:\n- Revenue growth declined from 15% to 9% year-over-year [Pages 12, 14].",
  "confidence": 0.84,
  "sources": [
    {
      "document_id": "uuid1",
      "document_name": "Annual_Report_2023.pdf",
      "page_start": 12,
      "page_end": 12,
      "chunk_id": "chunk-uuid-1"
    },
    {
      "document_id": "uuid2",
      "document_name": "Annual_Report_2024.pdf",
      "page_start": 14,
      "page_end": 14,
      "chunk_id": "chunk-uuid-2"
    }
  ],
  "conversation_id": "conv-uuid"
}
```

### Confidence Scoring

Confidence reflects answer reliability based on:

| Factor | Weight | Description |
|--------|--------|-------------|
| Retrieval relevance | 0-0.4 | Average similarity score of retrieved chunks |
| Citation coverage | 0-0.3 | Ratio of cited chunks to retrieved chunks |
| Source diversity | 0-0.2 | Number of distinct pages cited |
| Multi-doc coverage | 0-0.1 | Whether multiple documents contributed |

**Penalties:**
- Required regeneration: -0.15 (had citation issues on first attempt)

**Score never reaches 1.0** - maximum is 0.99 for perfect conditions.

### Conversation API

**Start a new conversation:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the company revenue?",
    "document_ids": ["uuid1"]
  }'
```

**Continue conversation:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How does that compare to last year?",
    "document_ids": ["uuid1", "uuid2"],
    "conversation_id": "returned-conv-uuid"
  }'
```

### Database Tables (Phase 5)

```sql
-- Conversation sessions
create table qa_conversations (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now()
);

-- Conversation messages
create table qa_messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references qa_conversations(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    cited_pages integer[],
    document_ids uuid[],
    created_at timestamptz not null default now()
);
```

### Hallucination Safety

Phase 5 preserves all Phase 4 guarantees:

- Every factual claim must have a citation
- Citations are validated against retrieved chunks
- Invalid citations trigger regeneration (max 2 retries)
- Ambiguous comparisons are explicitly refused
- Synthesis only allowed when both sources are cited

### Known Limitations

- **No cross-document entity resolution**: "Company X" in doc1 and "X Corp" in doc2 are not linked
- **Conversation memory is lightweight**: Only last exchange used for coreference
- **Rule-based rewriting**: Complex follow-ups may not resolve perfectly
- **Response time**: Multi-doc queries take 5-15 seconds (parallel retrieval helps)
- **Max 10 documents**: Per-request limit to prevent context overflow
