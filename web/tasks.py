"""
Background task handlers for document review and generation.
Uses threading for MVP instead of Celery to simplify deployment.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.executor import ReviewExecutor, ReviewMode
from rules.base_rule import RuleRegistry
from rules.loaders.rule_loader import RuleLoader
from llm.client import LLMClientFactory
from parsers.docx_parser import ParserFactory
from config.settings import settings
from web.time_utils import beijing_now_str
import json
import logging

logger = logging.getLogger(__name__)


def update_task_progress(db, task_id: int, progress: int, status: str = None):
    """Update task progress in database"""
    if status:
        db.update_review_task(task_id, progress=progress, status=status)
    else:
        db.update_review_task(task_id, progress=progress)


def run_review_task(task_id: int, filepath: str, rule_set: str, db):
    """Execute document review task in background thread"""
    try:
        logger.info(f"Starting review task {task_id} for {filepath} (rule_set={rule_set})")

        # Update status to processing
        update_task_progress(db, task_id, 0, 'processing')

        # Initialize components
        all_rules = RuleLoader.load_all_rules(profile="default")

        # 按规则集筛选
        if rule_set and rule_set != 'all':
            all_rules = [r for r in all_rules if r.source == rule_set]
        enabled_rules = [r for r in all_rules if r.enabled]
        rule_snapshot = {
            r.rule_id: {
                "rule_id": r.rule_id,
                "name": r.name,
                "code": r.code,
                "description": r.description,
                "logic": r.logic,
                "standard_ref": r.standard_ref,
                "severity": r.severity.value,
                "review_type": r.review_type.value,
                "source": r.source,
                "enabled": r.enabled,
            }
            for r in enabled_rules
        }

        llm_client = LLMClientFactory.create_client(settings.llm_provider)

        registry = RuleRegistry()
        for rule in all_rules:
            registry.register(rule)

        # Parse document
        update_task_progress(db, task_id, 10)
        parser = ParserFactory.get_parser(".docx")
        document = parser.parse(filepath)

        # Security classification check (pre-processing gate)
        update_task_progress(db, task_id, 15)
        from security.classification_detector import ClassificationDetector
        detector = ClassificationDetector(llm_client=llm_client)
        sec_result = detector.check(document)
        if sec_result.is_classified:
            logger.warning("Task %d blocked: classified content detected", task_id)
            db.update_review_task(
                task_id,
                status='blocked',
                error=sec_result.warning_message,
                completed_at=beijing_now_str()
            )
            return

        executor = ReviewExecutor(
            rule_registry=registry,
            llm_client=llm_client,
            mode=ReviewMode.BOTH
        )

        # Execute review
        update_task_progress(db, task_id, 50)
        result = executor.review_document(document)

        # Prepare result data
        update_task_progress(db, task_id, 90)
        sections_data = []
        for sr in result.section_results:
            issues = []
            for rr in sr.rule_results:
                if not rr.passed:
                    issues.append({
                        'rule_id': rr.rule_id,
                        'rule_name': rr.rule_name,
                        'rule_code': rule_snapshot.get(rr.rule_id, {}).get('code', ''),
                        'rule_source': rr.rule_source,
                        'severity': rr.severity.value,
                        'message': rr.message,
                        'suggestions': rr.suggestions,
                        'rule_reference': rr.rule_reference or rule_snapshot.get(rr.rule_id, {}).get('standard_ref', ''),
                        'rule_logic': rule_snapshot.get(rr.rule_id, {}).get('logic', ''),
                    })
            sections_data.append({
                'section_id': sr.section_id,
                'section_text': sr.section_text,
                'passed': sr.passed,
                'issues': issues,
            })

        result_data = {
            'passed': result.overall_passed,
            'total_issues': result.total_issues,
            'errors': result.errors,
            'warnings': result.warnings,
            'llm_issues': getattr(result, 'llm_issues', 0),
            'summary': result.summary,
            'review_time': beijing_now_str(),
            'review_duration': result.review_time,
            'rule_set': rule_set or 'all',
            'rule_snapshot': rule_snapshot,
            'sections': sections_data,
        }

        # Mark as completed using helper function for consistency
        db.update_review_task(
            task_id,
            result=json.dumps(result_data),
            status='completed',
            progress=100,
            completed_at=result_data['review_time']
        )

        logger.info(f"Review task {task_id} completed successfully")

    except Exception as e:
        logger.error(f"Review task {task_id} failed: {str(e)}")
        import traceback
        traceback.print_exc()

        # Mark as failed using helper function for consistency
        db.update_review_task(
            task_id,
            status='failed',
            error=str(e),
            completed_at=beijing_now_str()
        )
