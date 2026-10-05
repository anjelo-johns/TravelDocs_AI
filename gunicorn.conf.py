import os

# Automatically bind to whatever port Render (or local environment) specifies
port = os.getenv("PORT", "10000")
bind = f"0.0.0.0:{port}"
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = 2
timeout = 120
accesslog = "-"
errorlog = "-"
