# Stage 1: Builder
FROM python:3.13-slim-bookworm AS builder

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
# Based on Playwright's official Dockerfile for browser dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Browsers dependencies
    libwoff1 \
    libharfbuzz-icu0 \
    libwebp6 \
    libgstreamer-plugins-base1.0-0 \
    libgstreamer1.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libgbm1 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libatspi2.0-0 \
    libxkbcommon0 \
    libxshmfence-dev \
    libwayland-client0 \
    libwayland-egl1 \
    libwayland-cursor0 \
    xdg-utils \
    # Fonts
    fonts-liberation \
    fonts-noto-color-emoji \
    # Misc
    libasound2 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libevent-2.1-7 \
    libfontconfig1 \
    libfreetype6 \
    libglib2.0-0 \
    libjpeg62-turbo \
    libpng16-16 \
    libx11-6 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    # For Playwright install
    ca-certificates \
    curl \
    gnupg \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only requirements.txt to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Stage 2: Runtime
FROM python:3.13-slim-bookworm AS runtime

# Install Playwright runtime dependencies (minimal set)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libwoff1 \
    libharfbuzz-icu0 \
    libwebp6 \
    libgstreamer-plugins-base1.0-0 \
    libgstreamer1.0-0 \
    libxcomposite1 \
    libxrandr2 \
    libgbm1 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libatspi2.0-0 \
    libxkbcommon0 \
    libxshmfence-dev \
    libwayland-client0 \
    libwayland-egl1 \
    libwayland-cursor0 \
    xdg-utils \
    fonts-liberation \
    fonts-noto-color-emoji \
    libasound2 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libevent-2.1-7 \
    libfontconfig1 \
    libfreetype6 \
    libglib2.0-0 \
    libjpeg62-turbo \
    libpng16-16 \
    libx11-6 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN adduser --system --group appuser
USER appuser

# Set working directory
WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
# Copy Playwright browsers from builder stage
COPY --from=builder /ms-playwright /ms-playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copy application code
COPY --chown=appuser:appuser . .

# Expose ports (if any, e.g., for FastAPI or other services)
# EXPOSE 8000

# Health check (example, adjust as needed)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD python -c "import os; exit(os.path.exists('/app/main.py') and os.path.exists('/app/core/celery_config.py'))" || exit 1

# Entrypoint script (will be created later)
ENTRYPOINT ["/app/docker/scripts/entrypoint.sh"]
