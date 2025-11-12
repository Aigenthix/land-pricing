FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libatspi2.0-0 libxshmfence1 libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Use a requirements.txt because pyproject lacks a build-backend
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium browsers
RUN python -m playwright install chromium

# Copy app
COPY . .

# Expose the port provided by Render via $PORT (gunicorn.conf.py uses it)
ENV PORT=10000

# Start the Flask app with gunicorn
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:app"]