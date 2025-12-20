# Paper

A multimodal document processing system with AI capabilities. Paper provides a robust backend for uploading, validating, and managing PDF documents with plans for future AI-powered extraction and analysis features.

## Overview

Paper is built as a phased project where each phase adds new capabilities while maintaining stability:

- **Phase 0 (Complete)**: Infrastructure foundation with FastAPI, Supabase PostgreSQL, Redis, and Qdrant
- **Phase 1 (Complete)**: Document ingestion, validation, and persistent storage
- **Future Phases**: PDF text extraction, embeddings, vector search, and LLM integration

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend Framework** | Python 3.11, FastAPI, Uvicorn | Async REST API with automatic OpenAPI docs |
| **Database** | Supabase PostgreSQL | Document metadata storage with SSL encryption |
| **ORM** | SQLAlchemy 2.x (async) + asyncpg | Async database operations |
| **Cache** | Redis 7 | Session management and future caching needs |
| **Vector Database** | Qdrant | Future semantic search capabilities |
| **Validation** | Pydantic v2, PyMuPDF | Request/response validation and PDF integrity checks |
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

## API Reference

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API information and version |
| `GET` | `/health` | Health check for all services |
| `POST` | `/documents/upload` | Upload a PDF document |
| `GET` | `/documents` | List all documents |
| `GET` | `/documents/{id}` | Get document details by ID |

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
