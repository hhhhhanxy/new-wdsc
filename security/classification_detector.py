"""
涉密内容检测模块。

两层机制：
1. Layer 1：关键词+正则快速扫描
2. Layer 2：LLM 语义深度分析

检测到涉密内容后立即停止处理并提示用户。
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from rules.base_rule import TextPosition
from models.document import ParsedDocument

logger = logging.getLogger(__name__)

# 密级标识
CLASSIFICATION_MARKERS = {
    "绝密": [r'绝密', r'TOP\s*SECRET', r'绝密★', r'绝秘'],
    "机密": [r'机密', r'SECRET', r'机密★'],
    "秘密": [r'秘密', r'CONFIDENTIAL', r'秘密★'],
    "内部": [r'内部', r'INTERNAL', r'内部★', r'仅限内部', r'内部资料'],
}

# 军工相关标记
MILITARY_MARKERS = [
    r'军用',
    r'国防',
    r'武器',
    r'装备[^\s]*[号型]',
    r'部队[编号]',
    r'战场',
    r'作战',
]


@dataclass
class ClassificationResult:
    """涉密检测结果。"""
    is_classified: bool = False
    level: Optional[str] = None          # "绝密" / "机密" / "秘密" / "内部"
    markers_found: List[str] = field(default_factory=list)
    positions: List[TextPosition] = field(default_factory=list)
    confidence: float = 0.0
    llm_analysis: Optional[str] = None
    warning_message: str = ""


class ClassificationDetector:
    """两层涉密内容检测器。"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._compiled_markers = {
            level: [re.compile(p, re.IGNORECASE) for p in patterns]
            for level, patterns in CLASSIFICATION_MARKERS.items()
        }
        self._compiled_military = [re.compile(p, re.IGNORECASE) for p in MILITARY_MARKERS]

    def check(self, document: ParsedDocument) -> ClassificationResult:
        """
        执行两层检测。Layer 1 发现明确标记则立即返回，否则执行 Layer 2。
        """
        # Layer 1: 快速关键词扫描
        result = self._layer1_keyword_scan(document)
        if result.is_classified:
            logger.warning("Layer 1 检测到涉密标记: %s (%s)", result.markers_found, result.level)
            return result

        # Layer 2: LLM 语义分析
        if self.llm_client:
            result = self._layer2_llm_analysis(document, result)

        return result

    def check_text(self, text: str) -> ClassificationResult:
        """对纯文本执行涉密检测（用于生成内容的输出检测）。"""
        # Layer 1
        markers_found = []
        positions = []
        detected_level = None

        for level, patterns in self._compiled_markers.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    markers_found.append(match.group())
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    positions.append(TextPosition(
                        start_char=match.start(),
                        end_char=match.end(),
                        context_snippet=text[start:end]
                    ))
                    if not detected_level or level in ("绝密", "机密"):
                        detected_level = level

        if markers_found:
            return ClassificationResult(
                is_classified=True,
                level=detected_level,
                markers_found=markers_found,
                positions=positions,
                confidence=0.95,
                warning_message=self._build_warning(detected_level, markers_found)
            )

        return ClassificationResult(is_classified=False)

    def _layer1_keyword_scan(self, document: ParsedDocument) -> ClassificationResult:
        """Layer 1：正则扫描密级标识。"""
        markers_found = []
        positions = []
        detected_level = None
        priority = {"绝密": 4, "机密": 3, "秘密": 2, "内部": 1}

        for section in document.sections:
            text = section.text
            for level, patterns in self._compiled_markers.items():
                for pattern in patterns:
                    for match in pattern.finditer(text):
                        markers_found.append(match.group())
                        start = max(0, match.start() - 20)
                        end = min(len(text), match.end() + 20)
                        positions.append(TextPosition(
                            start_char=match.start(),
                            end_char=match.end(),
                            context_snippet=text[start:end]
                        ))
                        if not detected_level or priority.get(level, 0) > priority.get(detected_level, 0):
                            detected_level = level

        if markers_found:
            return ClassificationResult(
                is_classified=True,
                level=detected_level,
                markers_found=markers_found,
                positions=positions,
                confidence=0.95,
                warning_message=self._build_warning(detected_level, markers_found)
            )

        return ClassificationResult(is_classified=False)

    def _layer2_llm_analysis(self, document: ParsedDocument, layer1_result: ClassificationResult) -> ClassificationResult:
        """Layer 2：LLM 语义分析隐含涉密内容。"""
        try:
            prompt = f"""请分析以下文档内容，判断是否包含涉密信息或国家秘密。

【文档标题】
{document.title}

【文档内容（节选）】
{document.raw_text[:3000]}

【检查要点】
1. 是否包含国家秘密、军事秘密相关内容
2. 是否包含军工产品核心技术参数（具体型号、性能指标、工艺参数）
3. 是否包含保密资格相关信息
4. 是否暗示存在保密等级标识

【输出格式】
请严格按以下JSON格式输出，不要输出其他内容：
{{"is_classified": true或false, "confidence": 0.0到1.0, "level": "绝密或机密或秘密或内部或无", "reason": "判断依据"}}"""

            response = self.llm_client.generate(prompt)
            content = response.content.strip()

            # 提取JSON
            import json
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])
                is_classified = data.get('is_classified', False)
                confidence = data.get('confidence', 0.0)

                if is_classified and confidence >= 0.6:
                    level = data.get('level', '内部')
                    reason = data.get('reason', '')
                    layer1_result.is_classified = True
                    layer1_result.level = level
                    layer1_result.confidence = confidence
                    layer1_result.llm_analysis = reason
                    layer1_result.warning_message = self._build_warning(level, [], reason)
                    logger.warning("Layer 2 LLM 检测到疑似涉密内容: %s (confidence=%.2f)", level, confidence)

        except Exception as e:
            logger.error("Layer 2 LLM 分析失败: %s", e)

        return layer1_result

    def _build_warning(self, level: str, markers: List[str], reason: str = "") -> str:
        parts = [f"检测到疑似涉密内容（密级：{level}）。"]
        if markers:
            parts.append(f"发现标记：{', '.join(markers[:5])}。")
        if reason:
            parts.append(f"分析依据：{reason}。")
        parts.append("根据国家保密法规，已停止处理。请确认文档密级后重试。")
        return " ".join(parts)
