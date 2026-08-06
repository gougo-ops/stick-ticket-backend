FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Railway provides PORT env var; default to 8000
ENV PORT=8000

EXPOSE $PORT

# Start server
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
# force rebuild
