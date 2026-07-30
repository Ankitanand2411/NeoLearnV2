# ─── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install deps in a virtual env to keep the image clean
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ─── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source
COPY app/ ./app/

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# Cloud Run listens on $PORT (default 8080)
ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
