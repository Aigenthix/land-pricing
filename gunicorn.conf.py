import os

# Keep concurrency low to fit Render Free plan memory
workers = 1
threads = 2

# Bind to the PORT provided by the platform
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Allow long-running OCR/LLM calls
timeout = 180
graceful_timeout = 30
keepalive = 5

# Recycle workers to mitigate potential memory growth
max_requests = 50
max_requests_jitter = 10
