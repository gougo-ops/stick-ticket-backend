FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -- 2026-08-08 build -- force fresh source copy
RUN echo "Build timestamp: $(date)"

# Copy source code (modify any .py file to invalidate this layer)
COPY . .

# Render / Railway provide PORT env var; default to 8000 for local dev
ENV PORT=8000

EXPOSE $PORT

# Start server
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
