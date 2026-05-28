"""
Database models for the web application.
Uses SQLite for simplicity in MVP.
"""
import sqlite3
import threading
from typing import Optional, Dict, Any
import json


class Database:
    """SQLite database handler for MVP - thread safe via per-thread connections."""

    def __init__(self, db_path: str = 'web/database.db'):
        self.db_path = db_path
        self._local = threading.local()
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def init_db(self):
        """Create database tables"""
        # Ensure directory exists
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        cursor = self.conn.cursor()

        # Review tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                result TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        # Generate tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generate_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type TEXT NOT NULL,
                template_name TEXT NOT NULL,
                params TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                result_path TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        self.conn.commit()

    def get_review_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get review task by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM review_tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_review_task(self, filename: str, filepath: str, mode: str) -> int:
        """Create a new review task and return its ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO review_tasks (filename, filepath, mode, status)
            VALUES (?, ?, ?, 'pending')
        ''', (filename, filepath, mode))
        self.conn.commit()
        return cursor.lastrowid

    def update_review_task(self, task_id: int, **kwargs):
        """Update review task fields"""
        valid_fields = {'status', 'progress', 'result', 'error', 'completed_at'}
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not updates:
            return

        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        values = list(updates.values()) + [task_id]

        cursor = self.conn.cursor()
        cursor.execute(f'''
            UPDATE review_tasks SET {set_clause}
            WHERE id = ?
        ''', values)
        self.conn.commit()

    def get_generate_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get generate task by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM generate_tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_generate_task(self, doc_type: str, template_name: str, params: Dict[str, Any]) -> int:
        """Create a new generate task and return its ID"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO generate_tasks (doc_type, template_name, params, status)
            VALUES (?, ?, ?, 'pending')
        ''', (doc_type, template_name, json.dumps(params)))
        self.conn.commit()
        return cursor.lastrowid

    def update_generate_task(self, task_id: int, **kwargs):
        """Update generate task fields"""
        valid_fields = {'status', 'progress', 'result_path', 'error', 'completed_at'}
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not updates:
            return

        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        values = list(updates.values()) + [task_id]

        cursor = self.conn.cursor()
        cursor.execute(f'''
            UPDATE generate_tasks SET {set_clause}
            WHERE id = ?
        ''', values)
        self.conn.commit()

    def get_recent_review_tasks(self, limit: int = 5):
        """Get recent review tasks"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, filename, status, progress, created_at
            FROM review_tasks
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection"""
        self.conn.close()
