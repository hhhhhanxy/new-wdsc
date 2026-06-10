"""文档生成编排器。"""
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


def _safe_docx_filename(title: str) -> str:
    """Return a Windows-safe DOCX filename stem."""
    import re

    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(title or "").strip())
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    return stem[:120] or "generated_document"


@dataclass
class PipelineResult:
    """文档生成结果。"""
    generated_path: Optional[str] = None
    review_result: Optional[Any] = None
    passed_review: bool = False
    error: str = ""
    status: str = "pending"  # pending, generated, reviewing, passed, failed

    def to_dict(self) -> dict:
        return {
            "generated_path": self.generated_path,
            "passed_review": self.passed_review,
            "error": self.error,
            "status": self.status,
        }


def generate_document_only(
    doc_type,
    title: str,
    params: Dict[str, Any],
    llm_client,
    output_dir: str,
    progress_callback: Optional[Callable[[int, int, Any], None]] = None,
) -> PipelineResult:
    """
    Generate a document from a saved DOCX template asset.

    Review is intentionally not executed in the current generation MVP.
    """
    from generators.base_generator import GeneratorFactory

    result = PipelineResult()

    import os
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{_safe_docx_filename(title)}.docx")

    gen_name = params.get("generator", "template_docx")
    generator = GeneratorFactory.create(gen_name)
    try:
        generator.generate(
            title=title,
            params={**params, "doc_type": getattr(doc_type, "value", str(doc_type or ""))},
            llm_client=llm_client,
            output_path=output_path,
            progress_callback=progress_callback,
        )
        result.generated_path = output_path
        result.passed_review = True
        result.status = "generated"
    except Exception as e:
        result.status = "failed"
        result.error = f"生成失败: {e}"

    return result
