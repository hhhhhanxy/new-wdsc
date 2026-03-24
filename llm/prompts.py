from typing import List, Dict, Any, Optional
from jinja2 import Template


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
- 输出必须严格符合指定格式
- 不要输出任何额外解释或多余内容
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

【输出要求】
请严格按照以下JSON格式输出，不要输出任何额外内容：

{
    "passed": true,
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

如果无法生成JSON，请返回：
{"error": "无法解析"}
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

【审查要求】
1. 给出总体评价
2. 列出主要问题
3. 提供修改建议
4. 给出最终审查结论

【输出要求】
请严格按照以下JSON格式输出，不要输出任何额外内容：

{
    "summary": "总体评价",
    "issues": [
        {
            "description": "问题描述",
            "severity": "error/warning/info",
            "suggestion": "修改建议"
        }
    ],
    "suggestions": [
        "整体修改建议1",
        "整体修改建议2"
    ],
    "conclusion": "通过/不通过/需要修改"
}

如果无法生成JSON，请返回：
{"error": "无法解析"}
"""

DEFAULT_REVIEW_FOCUS = [
    "内容完整性（是否覆盖关键要点）",
    "格式规范性（是否符合文档规范）",
    "逻辑一致性（是否前后连贯）"
]

class ReviewPromptBuilder:
    def __init__(self):
        self.system_prompt = REVIEW_SYSTEM_PROMPT

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
            rules=rules,          # ✅ 关键：直接传 list
            review_focus=focus    # ✅ 关键
        )

    def build_section_review_prompt(
        self,
        section_text: str,
        rules: List[Dict[str, str]]
    ) -> str:
        template = PromptTemplate(REVIEW_SECTION_PROMPT)
        return template.render(
            section_text=section_text,
            rules=rules
        )