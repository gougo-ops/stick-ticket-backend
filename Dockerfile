FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Force cache invalidation: 2026-08-08-v2
ARG CACHE_BUST=20260808
# Copy source code
COPY . .

# Render / Railway provide PORT env var; default to 8000 for local dev
ENV PORT=8000

EXPOSE $PORT

# Start server
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
