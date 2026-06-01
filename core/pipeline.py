"""
审查-生成闭环编排器。

生成文档后自动执行五阶段审查，确保输出质量。
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from core.executor import PhasedDocumentReviewResult
from security.classification_detector import ClassificationDetector

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """闭环流水线结果。"""
    generated_path: Optional[str] = None
    review_result: Optional[PhasedDocumentReviewResult] = None
    passed_review: bool = False
    is_blocked: bool = False
    block_reason: str = ""
    status: str = "pending"  # pending, generated, reviewing, passed, failed, blocked

    def to_dict(self) -> dict:
        return {
            "generated_path": self.generated_path,
            "passed_review": self.passed_review,
            "is_blocked": self.is_blocked,
            "block_reason": self.block_reason,
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
    1. 安全检测（输入参数）
    2. 生成文档
    3. 安全检测（生成内容）
    4. 五阶段审查
    5. 返回结果
    """
    from generators.base_generator import GeneratorFactory
    from parsers.docx_parser import ParserFactory
    from core.phased_executor import PhasedReviewExecutor

    result = PipelineResult()

    # Step 1: 安全检测（输入）
    detector = ClassificationDetector(llm_client=llm_client)
    input_text = (
        f"{title} {params.get('description', '')} "
        f"{params.get('technical_params', '')} {params.get('generation_definition', '')}"
    )
    input_check = detector.check_text(input_text)
    if input_check.is_classified:
        result.is_blocked = True
        result.block_reason = input_check.warning_message
        result.status = "blocked"
        return result

    # Step 2: 生成文档
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
        result.block_reason = f"生成失败: {e}"
        return result

    # Step 3: 安全检测（输出）
    parser = ParserFactory.get_parser(".docx")
    document = parser.parse(output_path)
    if hasattr(doc_type, "value"):
        document.doc_type = doc_type

    output_check = detector.check(document)
    if output_check.is_classified:
        result.is_blocked = True
        result.block_reason = f"生成内容安全问题: {output_check.warning_message}"
        result.status = "blocked"
        # 删除不安全文件
        import os
        if os.path.exists(output_path):
            os.remove(output_path)
        return result

    # Step 4: 五阶段审查
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
