FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .

# Install build deps, curl for healthcheck, install python deps from requirements.txt, then cleanup
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m -u 1000 appuser

COPY . .
RUN chown -R appuser:appuser /app

USER appuser

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "api.main:app", "-b", "0.0.0.0:8000"]
