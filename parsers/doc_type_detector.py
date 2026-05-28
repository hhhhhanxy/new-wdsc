"""
文档类型自动识别。

基于关键词启发式 + LLM 兜底的双重检测。
"""
import logging
from typing import Optional, Dict, List

from models.document import ParsedDocument, DocumentType

logger = logging.getLogger(__name__)

# 文档类型关键词映射
TYPE_KEYWORDS: Dict[DocumentType, List[str]] = {
    DocumentType.REQUIREMENTS: [
        "需求", "需求分析", "功能需求", "性能需求", "需求规格",
        "需求追溯", "需求验证", "需求文档",
    ],
    DocumentType.GENERAL_CHARACTERISTICS: [
        "通用特性", "产品特性", "物理特性", "功能特性",
        "产品说明", "产品规范", "特性描述",
    ],
    DocumentType.TECHNICAL_SPECIFICATION: [
        "技术说明", "技术规范", "设计说明", "技术方案",
        "技术规格", "设计文档", "技术条件",
    ],
    DocumentType.VERIFICATION: [
        "验证", "测试验证", "试验报告", "验证确认",
        "测试报告", "检验报告", "验证方案",
    ],
}


class DocumentTypeDetector:
    """文档类型检测器。"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def detect(self, document: ParsedDocument) -> DocumentType:
        """自动检测文档类型。先关键词匹配，置信度低时回退 LLM。"""
        # 关键词匹配
        scores = self._keyword_score(document)
        if scores:
            best_type = max(scores, key=scores.get)
            if scores[best_type] >= 2:
                logger.info("关键词检测文档类型: %s (score=%d)", best_type.value, scores[best_type])
                return best_type

        # LLM 兜底
        if self.llm_client:
            return self._llm_detect(document)

        # 默认
        logger.info("无法确定文档类型，默认: technical_specification")
        return DocumentType.TECHNICAL_SPECIFICATION

    def _keyword_score(self, document: ParsedDocument) -> Dict[DocumentType, int]:
        """基于关键词计算各类型的匹配分数。"""
        text = (document.title + " " + document.raw_text[:2000]).lower()
        scores = {}
        for doc_type, keywords in TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[doc_type] = score
        return scores

    def _llm_detect(self, document: ParsedDocument) -> DocumentType:
        """通过 LLM 判断文档类型。"""
        try:
            import json
            prompt = f"""请判断以下文档属于哪种类型。

文档标题：{document.title}
文档内容（节选）：{document.raw_text[:1500]}

类型选项：
1. requirements - 需求文档（描述产品需求、功能需求、性能需求）
2. general_characteristics - 通用特性文档（描述产品物理特性、功能特性、性能参数）
3. technical_specification - 技术说明书（描述系统设计、接口定义、安全性分析）
4. verification - 验证文档（描述验证方法、测试结果、结论）

请仅输出类型标识符（如 requirements），不要输出其他内容。"""

            response = self.llm_client.generate(prompt)
            content = response.content.strip().lower()

            for doc_type in DocumentType:
                if doc_type.value in content:
                    logger.info("LLM 检测文档类型: %s", doc_type.value)
                    return doc_type

        except Exception as e:
            logger.error("LLM 文档类型检测失败: %s", e)

        return DocumentType.TECHNICAL_SPECIFICATION
