# Paper

A multimodal document processing system with AI capabilities.

## Phase 0 — Infrastructure & Core Skeleton

This phase establishes the foundational infrastructure:

- FastAPI backend running in Docker
- Supabase PostgreSQL (remote, SSL-enabled)
- Redis (local container)
- Qdrant vector database (local container)
- Health check endpoint verifying all dependencies
- Automatic database table creation at startup

## Tech Stack

- Python 3.11
- FastAPI + Uvicorn
- SQLAlchemy 2.x (async) + asyncpg
- Pydantic v2 + pydantic-settings
- Redis 7
- Qdrant
- Docker + Docker Compose v2

## Prerequisites

- Docker and Docker Compose v2
- Supabase project with PostgreSQL database

## Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd paper
```

2. Create environment file from example:

```bash
cp .env.example .env
```

3. Configure your Supabase credentials in `.env`:

```
SUPABASE_DB_HOST=your-project-id.supabase.co
SUPABASE_DB_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=your_password
SUPABASE_DB_SSL=true
```

## Running the Application

Start all services with a single command:

```bash
docker-compose -f infrastructure/docker-compose.yml up --build
```

To run in detached mode:

```bash
docker-compose -f infrastructure/docker-compose.yml up --build -d
```

To stop all services:

```bash
docker-compose -f infrastructure/docker-compose.yml down
```

## Verifying Health

### API Root

```bash
curl http://localhost:8000/
```

Expected response:

```json
{
  "name": "Paper API",
  "version": "0.0.1"
}
```

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response (all healthy):

```json
{
  "status": "ok",
  "services": {
    "database": "connected",
    "redis": "connected",
    "qdrant": "connected"
  }
}
```

If any service is unreachable, returns HTTP 503:

```json
{
  "status": "degraded",
  "services": {
    "database": "unreachable",
    "redis": "connected",
    "qdrant": "connected"
  }
}
```

### Qdrant Dashboard

Access the Qdrant dashboard at: http://localhost:6333/dashboard

## Phase 1 — Document Ingestion & Storage

Phase 1 adds document upload, validation, and storage capabilities:

- Upload PDF documents via REST API
- Validate PDF integrity (reject corrupted/password-protected files)
- Store files persistently on disk (Docker volume)
- Track document metadata in Supabase PostgreSQL
- Document status lifecycle: `uploaded` → `validated` / `failed`

### Upload a Document

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@/path/to/your/document.pdf"
```

Success response:

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "status": "validated"
}
```

Error response (invalid PDF):

```json
{
  "error": "Invalid PDF file",
  "detail": "Password-protected PDFs are not supported"
}
```

### List Documents

```bash
curl http://localhost:8000/documents
```

Response:

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "document.pdf",
    "status": "validated",
    "file_size": 1048576,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

### Get Document Details

```bash
curl http://localhost:8000/documents/550e8400-e29b-41d4-a716-446655440000
```

Response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "stored_filename": "550e8400-e29b-41d4-a716-446655440000.pdf",
  "file_size": 1048576,
  "mime_type": "application/pdf",
  "page_count": 10,
  "status": "validated",
  "error_message": null,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### File Storage

Uploaded files are stored in a Docker volume mounted at `/data/documents`. Files persist across container restarts.

## Project Structure

```
paper/
├── backend/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   └── documents.py
│   │   └── dependencies.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── redis.py
│   │   └── storage.py
│   ├── models/
│   │   └── document.py
│   ├── schemas/
│   │   └── document.py
│   ├── requirements.txt
│   └── Dockerfile
├── infrastructure/
│   └── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```
