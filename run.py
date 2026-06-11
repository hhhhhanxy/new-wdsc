"""
Application launcher for the web interface.
"""
from web.app import app
import os
from pathlib import Path

if __name__ == '__main__':
    project_root = Path(__file__).resolve().parent
    os.environ.setdefault('UV_CACHE_DIR', str(project_root / '.uv-cache'))

    port = 5000
    host = '127.0.0.1'
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    use_reloader = False
    interrupted = app.db.interrupt_running_generate_tasks('服务重启，原生成任务已中断')

    print(f"Starting Web Interface on http://{host}:{port}")
    print(f"Upload directory: {app.config['UPLOAD_FOLDER']}")
    print(f"Database: {app.db.db_path}")
    print(f"UV cache: {os.environ.get('UV_CACHE_DIR')}")
    print(f"Debug: {debug}, Reloader: {use_reloader}")
    if interrupted:
        print(f"Interrupted stale generation tasks: {interrupted}")

    app.run(debug=debug, host=host, port=port, use_reloader=use_reloader)
