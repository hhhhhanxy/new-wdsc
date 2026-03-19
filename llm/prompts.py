from typing import List, Dict, Any, Optional
from jinja2 import Template
from llm.client import BaseLLMClient, LLMResponse


class PromptTemplate:
    def __init__(self, template: str):
        self.template = Template(template)
    
    def render(self, **kwargs) -> str:
        return self.template.render(**kwargs)


REVIEW_SYSTEM_PROMPT = """
你是一名航空作动系统领域的高级工程专家，熟悉适航规范、设计报告和工程文档审查标准。

你的审查必须：
- 使用专业术语
- 避免口语化表达
- 给出工程可执行的修改建议
"""

REVIEW_SECTION_PROMPT = """请审查以下文档片段：

【文档片段】
{{ section_text }}

【审查规则】
{% for rule in rules %}
{{ loop.index }}. {{ rule.name }}: {{ rule.description }}
{% endfor %}

【审查要求】
1. 检查内容是否符合上述规则
2. 指出存在的问题
3. 提供具体的修改建议
4. 给出审查结论（通过/不通过/需要修改）

请以JSON格式返回审查结果：
{
    "passed": true/false,
    "issues": [
        {
            "rule_id": "规则ID",
            "description": "问题描述",
            "severity": "error/warning/info",
            "suggestion": "修改建议"
        }
    ],
    "summary": "审查总结"
}
"""

REVIEW_DOCUMENT_PROMPT = """请对以下文档进行全面审查：

【文档标题】
{{ document_title }}

【文档内容】
{{ document_content }}

【审查规则】
{% for rule in rules %}
{{ loop.index }}. {{ rule.name }}: {{ rule.description }}
{% endfor %}

【审查重点】
{% for focus in review_focus %}
- {{ focus }}
{% endfor %}

请提供完整的审查报告，包括：
1. 总体评价
2. 发现的问题列表
3. 修改建议
4. 审查结论
"""

DEFAULT_REVIEW_FOCUS = [
    "内容完整性（是否覆盖关键要点）",
    "格式规范性（是否符合文档规范）",
    "逻辑一致性（是否前后连贯）"
]

class ReviewPromptBuilder:
    def __init__(self):
        self.system_prompt = REVIEW_SYSTEM_PROMPT

    def _format_focus(self, review_focus: List[str]) -> str:
        return "\n".join([f"{i+1}. {f}" for i, f in enumerate(review_focus)])


    def build_document_review_prompt(
        self,
        document_title: str,
        document_content: str,
        rules: List[Dict[str, str]],
        review_focus: List[str] = None
    ) -> str:
        template = PromptTemplate(REVIEW_DOCUMENT_PROMPT)

        focus = review_focus or DEFAULT_REVIEW_FOCUS

        return template.render(
            document_title=document_title,
            document_content=document_content,
            rules=self._format_rules(rules),
            review_focus=self._format_focus(focus)
        )