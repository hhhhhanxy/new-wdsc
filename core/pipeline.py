"""
审查-生成闭环编排器。

生成文档后自动执行审查，确保输出质量。
"""
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

from core.executor import PhasedDocumentReviewResult
logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """闭环流水线结果。"""
    generated_path: Optional[str] = None
    review_result: Optional[PhasedDocumentReviewResult] = None
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


def generate_and_review(
    doc_type,
    title: str,
    params: Dict[str, Any],
    llm_client,
    rule_registry,
    output_dir: str,
) -> PipelineResult:
    """
    审查-生成闭环：
    1. 生成文档
    2. 审查生成结果
    3. 返回结果
    """
    from generators.base_generator import GeneratorFactory
    from parsers.docx_parser import ParserFactory
    from core.phased_executor import PhasedReviewExecutor

    result = PipelineResult()

    # Step 1: 生成文档
    import os
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{title}.docx")

    gen_name = params.get("generator", "user_defined_docx")
    generator = GeneratorFactory.create(gen_name)
    try:
        generator.generate(
            title=title,
            params={**params, "doc_type": getattr(doc_type, "value", str(doc_type or ""))},
            llm_client=llm_client,
            output_path=output_path,
        )
        result.generated_path = output_path
        result.status = "generated"
    except Exception as e:
        result.status = "failed"
        result.error = f"生成失败: {e}"
        return result

    # Step 2: 解析生成内容
    parser = ParserFactory.get_parser(".docx")
    document = parser.parse(output_path)
    if hasattr(doc_type, "value"):
        document.doc_type = doc_type

    # Step 3: 审查生成内容
    result.status = "reviewing"
    executor = PhasedReviewExecutor(
        rule_registry=rule_registry,
        llm_client=llm_client,
        mode="both",
    )
    review_result = executor.review_document(document)
    result.review_result = review_result
    result.passed_review = review_result.overall_passed
    result.status = "passed" if review_result.overall_passed else "failed"

    return result
