"""
Tests for background task execution
"""
import os
import tempfile
import time
import threading
from web.tasks import run_review_task
from web.models import Database

def test_review_task_updates_database():
    """Test that review task updates database with progress and results"""
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmpdir, 'test.db')
        db = Database(db_path)

        # Create a test task
        task_id = db.create_review_task('test.docx', '/fake/path.docx', 'both')

        # Run review task in background thread
        thread = threading.Thread(target=run_review_task, args=(task_id, '/fake/path.docx', 'both', db))
        thread.start()

        # Wait for task to complete (will fail due to fake path, but that's expected)
        thread.join(timeout=5)

        # Verify task was updated
        task = db.get_review_task(task_id)
        assert task is not None
        assert task['status'] in ['processing', 'completed', 'failed']
        assert task['progress'] >= 0

        # If task failed, verify error was logged
        if task['status'] == 'failed':
            assert task['error'] is not None
            assert 'Package not found' in task['error'] or 'fake/path.docx' in task['error']

        # Close database before cleanup
        db.close()

    finally:
        # Cleanup temp directory
        import shutil
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except:
            pass
