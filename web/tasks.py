"""
Background task handlers for document review and generation.
Uses threading for MVP instead of Celery to simplify deployment.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.executor import ReviewExecutor
from rules.loaders.rule_loader import RuleLoader
from llm.client import LLMClientFactory
from parsers.docx_parser import ParserFactory
import json
import logging

logger = logging.getLogger(__name__)


def update_task_progress(db, task_id: int, progress: int, status: str = None):
    """Update task progress in database"""
    if status:
        db.update_review_task(task_id, progress=progress, status=status)
    else:
        db.update_review_task(task_id, progress=progress)


def run_review_task(task_id: int, filepath: str, mode: str, db):
    """Execute document review task in background thread"""
    try:
        logger.info(f"Starting review task {task_id} for {filepath}")

        # Update status to processing
        update_task_progress(db, task_id, 0, 'processing')

        # Initialize components
        rules = RuleLoader.load_all_rules(profile="aviation")
        llm_client = LLMClientFactory.create_client("siliconflow")
        executor = ReviewExecutor(
            rule_registry=None,  # Will load rules directly
            llm_client=llm_client,
            use_llm=(mode != 'rule_only')
        )

        # Parse document
        update_task_progress(db, task_id, 10)
        parser = ParserFactory.get_parser(".docx")
        document = parser.parse(filepath)

        # Load rules into registry
        from rules.base_rule import RuleRegistry
        registry = RuleRegistry()
        for rule in rules:
            registry.register(rule)
        executor.rule_registry = registry

        # Execute review
        update_task_progress(db, task_id, 50)
        result = executor.review_document(document)

        # Prepare result data
        update_task_progress(db, task_id, 90)
        result_data = {
            'passed': result.overall_passed,
            'total_issues': result.total_issues,
            'errors': result.errors,
            'warnings': result.warnings,
            'llm_issues': getattr(result, 'llm_issues', 0),
            'summary': result.summary
        }

        # Mark as completed
        import sqlite3
        cursor = db.conn.cursor()
        cursor.execute('''
            UPDATE review_tasks
            SET result = ?, status = 'completed', progress = 100, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (json.dumps(result_data), task_id))
        db.conn.commit()

        logger.info(f"Review task {task_id} completed successfully")

    except Exception as e:
        logger.error(f"Review task {task_id} failed: {str(e)}")
        import traceback
        traceback.print_exc()

        # Mark as failed
        cursor = db.conn.cursor()
        cursor.execute('''
            UPDATE review_tasks
            SET status = 'failed', error = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (str(e), task_id))
        db.conn.commit()
