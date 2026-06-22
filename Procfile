# Procfile — Zeabur 部署入口
# Zeabur 自动使用 Gunicorn 作为 WSGI 服务器
# 如果 Zeabur 识别为 Python 项目，会自动执行 python main.py
# 下面的 web 命令作为显式声明
web: gunicorn -c gunicorn.conf.py wsgi:app
