"""
Production-style WSGI launcher for intranet deployment.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from waitress import serve

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")
os.environ.setdefault("UV_CACHE_DIR", str(project_root / ".uv-cache"))

from web.app import app


if __name__ == "__main__":
    host = os.environ.get("WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB_PORT", "5000"))
    threads = int(os.environ.get("WEB_THREADS", "8"))
    interrupted = app.db.interrupt_running_generate_tasks("服务重启，原生成任务已中断")

    print(f"Starting Web Interface with Waitress on http://{host}:{port}")
    print(f"Upload directory: {app.config['UPLOAD_FOLDER']}")
    print(f"Database: {app.db.db_path}")
    print(f"UV cache: {os.environ.get('UV_CACHE_DIR')}")
    print(f"Threads: {threads}")
    if interrupted:
        print(f"Interrupted stale generation tasks: {interrupted}")

    serve(app, host=host, port=port, threads=threads)
