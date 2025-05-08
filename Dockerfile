FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies required for Railway
RUN pip install --no-cache-dir \
    uvicorn \
    gunicorn \
    asyncpg \
    python-dotenv

# Copy application code
COPY . .

# Health check for Railway
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Create directory for logs
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Command to run both bots (through supervisor or script)
CMD ["sh", "-c", "python -m src.main & python -m src.chat_bot.main & wait"]

# Expose port for Health check
EXPOSE 8080 