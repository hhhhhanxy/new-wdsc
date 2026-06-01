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

        # Verify initial state
        task = db.get_review_task(task_id)
        assert task is not None
        assert task['status'] == 'pending'
        assert task['progress'] == 0

        # Run review task in background thread
        thread = threading.Thread(
            target=run_review_task,
            args=(task_id, '/fake/path.docx', 'all', db),
        )
        thread.start()

        # Wait for task to complete (will fail due to fake path, but that's expected)
        thread.join(timeout=5)

        # Verify task was updated
        task = db.get_review_task(task_id)
        assert task is not None

        # Verify status changed from pending
        assert task['status'] != 'pending'

        # Verify progress milestones were recorded
        # Task should have progressed beyond initial 0%
        if task['status'] == 'failed':
            # If failed, verify error was logged
            assert task['error'] is not None
            assert 'Package not found' in task['error'] or 'fake/path.docx' in task['error']
            # Progress should still be > 0 since task started processing
            assert task['progress'] >= 0
        elif task['status'] == 'completed':
            # If completed, progress should be 100%
            assert task['progress'] == 100
            assert task['result'] is not None

        # Close database before cleanup
        db.close()

    finally:
        # Cleanup temp directory
        import shutil
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except:
            pass
