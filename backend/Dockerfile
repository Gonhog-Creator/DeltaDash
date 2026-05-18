FROM python:3.11-slim

WORKDIR /app

# Set environment variables for Python
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN mkdir -p /app/storage/uploads /app/storage/material_docs /app/storage/reports /app/storage/model_artifacts

# Make docker-entrypoint.sh executable
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
