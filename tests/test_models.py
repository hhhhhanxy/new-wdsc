import os
import tempfile
import sqlite3
from web.models import Database

def test_database_init_creates_tables():
    """Test that Database initialization creates required tables"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = Database(db_path)

        # Check that tables exist
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('review_tasks', 'generate_tasks')
        """)
        tables = {row[0] for row in cursor.fetchall()}

        assert 'review_tasks' in tables
        assert 'generate_tasks' in tables

        # Close database connection before cleanup
        db.close()

def test_create_and_get_review_task():
    """Test creating and retrieving a review task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = Database(db_path)

        task_id = db.create_review_task('test.docx', '/path/to/test.docx', 'both')
        assert task_id > 0

        task = db.get_review_task(task_id)
        assert task is not None
        assert task['filename'] == 'test.docx'
        assert task['status'] == 'pending'

        # Close database connection before cleanup
        db.close()

def test_update_review_task():
    """Test updating a review task"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = Database(db_path)

        task_id = db.create_review_task('test.docx', '/path/to/test.docx', 'both')
        db.update_review_task(task_id, status='processing', progress=50)

        task = db.get_review_task(task_id)
        assert task['status'] == 'processing'
        assert task['progress'] == 50

        # Close database connection before cleanup
        db.close()


def test_update_review_task_progress_detail_fields():
    """Test updating detailed review progress fields"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = Database(db_path)

        task_id = db.create_review_task('test.docx', '/path/to/test.docx', 'both')
        db.update_review_task(
            task_id,
            status='processing',
            progress=62,
            progress_stage='review',
            progress_message='正在审查章节 10/33',
            current_section=10,
            total_sections=33,
        )

        task = db.get_review_task(task_id)
        assert task['status'] == 'processing'
        assert task['progress'] == 62
        assert task['progress_stage'] == 'review'
        assert task['progress_message'] == '正在审查章节 10/33'
        assert task['current_section'] == 10
        assert task['total_sections'] == 33

        db.close()


def test_generate_task_progress_detail_and_recent_records():
    """Test updating detailed generation progress fields and listing history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        db = Database(db_path)

        task_id = db.create_generate_task(
            doc_type='requirements',
            template_name='需求文档模板',
            params={'title': '需求文档'},
        )
        db.update_generate_task(
            task_id,
            status='processing',
            progress=48,
            progress_stage='generating',
            progress_message='正在处理章节 3/9：接口要求',
            current_section=3,
            total_sections=9,
        )

        task = db.get_generate_task(task_id)
        recent = db.get_recent_generate_tasks(limit=3)

        assert task['progress'] == 48
        assert task['progress_stage'] == 'generating'
        assert task['progress_message'] == '正在处理章节 3/9：接口要求'
        assert task['current_section'] == 3
        assert task['total_sections'] == 9
        assert recent[0]['id'] == task_id
        assert db.count_generate_tasks() == 1

        deleted = db.delete_generate_task(task_id)
        assert deleted == 1
        assert db.get_generate_task(task_id) is None

        db.close()
