FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies first (layer caching)
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Create non-root user and data directory
RUN useradd -m appuser && \
    mkdir -p /data && \
    chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

CMD ["uvicorn", "forgeserver.main:app", "--host", "0.0.0.0", "--port", "8000"]
