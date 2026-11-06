# Multi-stage Dockerfile for Discord Music Bot
# Stage 1: Build dependencies
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies to a dedicated prefix for clean copying
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# Stage 2: Minimal runtime image
FROM python:3.12-slim-bookworm AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FFMPEG_PATH=ffmpeg

# Install runtime system packages: ffmpeg, libopus, and ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Run as an unprivileged non-root user
RUN groupadd -g 10001 botgroup && \
    useradd -u 10001 -g botgroup -d /app -s /usr/sbin/nologin botuser

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source code
COPY --chown=botuser:botgroup src/ ./src/
COPY --chown=botuser:botgroup main.py ./

USER botuser

CMD ["python", "main.py"]
