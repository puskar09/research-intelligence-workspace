FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for compiling packages like psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend directory
COPY backend/ ./backend/

EXPOSE 8001

CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8001}"
