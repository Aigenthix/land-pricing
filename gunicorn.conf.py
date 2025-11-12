import os
workers = 1
threads = 2
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
