# Paper

A multimodal document processing system with AI capabilities.

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd paper
cp .env.example .env
# Edit .env with your Supabase credentials

# Run
docker-compose -f infrastructure/docker-compose.yml up --build
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | Supabase PostgreSQL (async via SQLAlchemy 2.x + asyncpg) |
| Cache | Redis 7 |
| Vector DB | Qdrant |
| Validation | Pydantic v2 |
| Container | Docker + Docker Compose v2 |

## Prerequisites

- Docker and Docker Compose v2
- Supabase project with PostgreSQL database

## Configuration

Create `.env` from the example and configure:

```bash
cp .env.example .env
```

Required variables:

| Variable | Description |
|----------|-------------|
| `SUPABASE_DB_HOST` | Your Supabase project host |
| `SUPABASE_DB_PASSWORD` | Database password |
| `DOCUMENT_STORAGE_PATH` | Path for uploaded files (default: `/data/documents`) |
| `MAX_UPLOAD_SIZE_MB` | Max upload size in MB (default: `50`) |

## Running

```bash
# Start all services
docker-compose -f infrastructure/docker-compose.yml up --build

# Detached mode
docker-compose -f infrastructure/docker-compose.yml up --build -d

# Stop
docker-compose -f infrastructure/docker-compose.yml down
```

## API Reference

### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/health` | GET | Service health check |

```bash
# Check health
curl http://localhost:8000/health
```

### Documents

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/documents/upload` | POST | Upload PDF |
| `/documents` | GET | List all documents |
| `/documents/{id}` | GET | Get document details |

#### Upload

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@document.pdf"
```

#### List

```bash
curl http://localhost:8000/documents
```

#### Get Details

```bash
curl http://localhost:8000/documents/{document_id}
```

### Response Examples

**Upload Success:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "status": "validated"
}
```

**Document Details:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "file_size": 1048576,
  "mime_type": "application/pdf",
  "page_count": 10,
  "status": "validated",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Health Check:**
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

## Document Lifecycle

```
Upload → Validation → validated / failed
```

- **validated**: PDF is valid and stored
- **failed**: PDF rejected (corrupted, password-protected, or invalid)

## Storage

- Files stored in Docker volume at `/data/documents`
- Persists across container restarts
- Max file size: 50 MB (configurable)
- Supported format: PDF only

## External Services

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |

## Project Structure

```
paper/
├── backend/
│   ├── api/
│   │   ├── main.py
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── health.py
│   │       └── documents.py
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
└── README.md
```
