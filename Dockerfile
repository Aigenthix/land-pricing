# Use Python 3.10 base image (matches uv venv Python version)
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for the application
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN uv venv && \
    . .venv/bin/activate && \
    uv sync --frozen

# Install Playwright browsers
RUN . .venv/bin/activate && \
    playwright install && \
    playwright install-deps

# Copy application files
COPY . .

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Activate virtual environment and set PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Expose port 5001
EXPOSE 5001

# Set environment variable for port (can be overridden)
ENV PORT=5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5001/ || exit 1

# Run with gunicorn (production-ready)
CMD ["gunicorn", "--workers", "1", "--threads", "2", "--bind", "0.0.0.0:5001", "--timeout", "120", "main:app"]

