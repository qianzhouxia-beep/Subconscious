# Gunicorn 生产环境配置
# 启动命令: gunicorn -c gunicorn.conf.py wsgi:app

import os

# Worker 配置
workers = int(os.environ.get("GUNICORN_WORKERS", "4"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
worker_class = "gthread"

# 绑定地址
bind = f"0.0.0.0:{os.environ.get('PORT', '3000')}"

# 超时设置（AI API 可能耗时较长）
timeout = 120
graceful_timeout = 30
keepalive = 5

# 日志
accesslog = "-"       # stdout
errorlog = "-"        # stderr
loglevel = os.environ.get("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sμs'

# 进程命名
proc_name = "subconscious-mirror"

# 安全：限制请求大小
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
limit_request_body = 10485760  # 10MB

# 优雅重启
max_requests = 10000
max_requests_jitter = 1000
