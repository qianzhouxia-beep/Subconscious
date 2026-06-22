"""WSGI entry point for production deployment (gunicorn)."""
from main import app

# Gunicorn 通过 `gunicorn wsgi:app` 启动
# 不在此处调用 app.run()，避免开发服务器冲突
