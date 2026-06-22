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
from core.utils import should_use_llm_check
from llm.client import LLMClientFactory
from parsers.docx_parser import ParserFactory
from config.settings import settings
from web.time_utils import beijing_now_str
import json
import logging
import time
import hashlib

logger = logging.getLogger(__name__)


class ReviewTaskCanceled(Exception):
    """Raised when a review task is canceled by the user."""


def wait_if_paused(db, task_id: int):
    """Block the worker while the task is paused by the user."""
    while True:
        task = db.get_review_task(task_id)
        if not task:
            raise ReviewTaskCanceled("审查任务已删除")
        if task.get('status') == 'canceled':
            raise ReviewTaskCanceled("审查已停止")
        if task.get('status') != 'paused':
            return
        time.sleep(1)


def update_task_progress(
    db,
    task_id: int,
    progress: int,
    status: str = None,
    stage: str = None,
    message: str = None,
    current_section: int = None,
    total_sections: int = None,
):
    """Update task progress in database"""
    wait_if_paused(db, task_id)
    payload = {
        'progress': progress,
        'progress_stage': stage,
        'progress_message': message,
        'current_section': current_section,
        'total_sections': total_sections,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    if status:
        payload['status'] = status
    db.update_review_task(task_id, **payload)


def run_review_task(task_id: int, filepath: str, rule_set: str, db):
    """Execute document review task in background thread"""
    try:
        logger.info(f"Starting review task {task_id} for {filepath} (rule_set={rule_set})")

        # Update status to processing
        update_task_progress(
            db,
            task_id,
            0,
            'processing',
            stage='init',
            message='正在初始化审查任务',
            current_section=0,
            total_sections=0,
        )

        # Initialize components
        update_task_progress(db, task_id, 5, stage='rules', message='正在加载审查规则')
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
                "scope": r.scope.value if hasattr(r.scope, "value") else str(r.scope or "all"),
                "target_headings": r.target_headings,
                "required_elements": r.required_elements,
                "params": r.params,
            }
            for r in enabled_rules
        }

        llm_rules = [r for r in enabled_rules if should_use_llm_check(r)]
        llm_client = None
        if llm_rules:
            update_task_progress(db, task_id, 8, stage='llm', message='正在初始化大模型客户端')
            llm_client = LLMClientFactory.create_client(settings.llm_provider)
        else:
            update_task_progress(db, task_id, 8, stage='rules', message='本次审查不需要调用大模型')

        registry = RuleRegistry()
        for rule in all_rules:
            registry.register(rule)

        # Parse document
        update_task_progress(db, task_id, 10, stage='parse', message='正在解析文档')
        parser = ParserFactory.get_parser(".docx")
        document = parser.parse(filepath)

        total_sections = len(document.sections)
        update_task_progress(
            db,
            task_id,
            15,
            stage='parsed',
            message=f'文档解析完成，共 {total_sections} 个章节',
            current_section=0,
            total_sections=total_sections,
        )

        executor = ReviewExecutor(
            rule_registry=registry,
            llm_client=llm_client,
            mode=ReviewMode.BOTH if llm_rules else ReviewMode.RULE_ONLY
        )

        # Execute review
        update_task_progress(
            db,
            task_id,
            50,
            stage='review',
            message=f'正在执行审查，共 {total_sections} 个章节',
            current_section=0,
            total_sections=total_sections,
        )
        def update_section_progress(done: int, total: int):
            if total <= 0:
                return
            progress = 50 + int((done / total) * 38)
            update_task_progress(
                db,
                task_id,
                min(progress, 88),
                stage='review',
                message=f'正在审查章节 {done}/{total}',
                current_section=done,
                total_sections=total,
            )

        result = executor.review_document(
            document,
            context={
                "pause_callback": lambda: wait_if_paused(db, task_id),
                "progress_callback": update_section_progress,
            }
        )

        # Prepare result data
        update_task_progress(
            db,
            task_id,
            90,
            stage='report',
            message='正在整理审查结果',
            current_section=total_sections,
            total_sections=total_sections,
        )
        sections_data = []
        for sr in result.section_results:
            issues = []
            for issue_index, rr in enumerate(sr.rule_results, start=1):
                if not rr.passed:
                    issue_fingerprint = "|".join([
                        str(sr.section_id or ""),
                        str(rr.rule_id or ""),
                        str(rr.rule_name or ""),
                        str(rr.message or ""),
                        str(issue_index),
                    ])
                    issues.append({
                        'issue_id': hashlib.sha1(issue_fingerprint.encode('utf-8')).hexdigest()[:16],
                        'review_status': 'pending',
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
            progress_stage='completed',
            progress_message='审查完成',
            current_section=total_sections,
            total_sections=total_sections,
            completed_at=result_data['review_time']
        )

        logger.info(f"Review task {task_id} completed successfully")

    except ReviewTaskCanceled as e:
        logger.info(f"Review task {task_id} canceled: {str(e)}")
        task = db.get_review_task(task_id)
        if task and task.get('status') != 'canceled':
            db.update_review_task(
                task_id,
                status='canceled',
                error=str(e),
                progress_stage='canceled',
                progress_message=str(e),
                completed_at=beijing_now_str()
            )

    except Exception as e:
        logger.error(f"Review task {task_id} failed: {str(e)}")
        import traceback
        traceback.print_exc()

        # Mark as failed using helper function for consistency
        db.update_review_task(
            task_id,
            status='failed',
            progress=100,
            error=str(e),
            progress_stage='failed',
            progress_message='审查失败',
            completed_at=beijing_now_str()
        )
