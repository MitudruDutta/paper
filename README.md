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

## Project Structure

```
paper/
├── backend/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   └── health.py
│   │   └── dependencies.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── redis.py
│   ├── models/
│   │   └── document.py
│   ├── requirements.txt
│   └── Dockerfile
├── infrastructure/
│   └── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```
