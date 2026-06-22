# Subconscious Mirror — 启动脚本
# 自动检测环境并选择最佳启动方式

import os
import sys

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3000))
    is_production = os.environ.get("FLASK_ENV", "production") == "production"
    
    if is_production:
        # 生产环境：使用 gunicorn（如果可用）
        try:
            import gunicorn.app.base
            from gunicorn.app.wsgiapp import WSGIApplication
            print(f"[Mirror] Starting production server on port {port} with gunicorn...")
            sys.argv = ['gunicorn', '-c', 'gunicorn.conf.py', 'wsgi:app']
            WSGIApplication().run()
        except ImportError:
            print("[Mirror] Gunicorn not found, falling back to Flask (NOT for production!)")
            from main import app
            app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # 开发环境：使用 Flask 内置服务器
        print(f"[Mirror] Starting development server on port {port}...")
        from main import app
        app.run(host='0.0.0.0', port=port, debug=True)
