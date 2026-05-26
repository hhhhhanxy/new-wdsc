"""
Prompt 系统优化版本
改进：
1. 添加 Few-Shot 示例
2. 添加思维链（Chain of Thought）引导
3. 改进规则描述格式
4. 添加输出验证指令
5. 支持动态 prompt 构建
6. 添加领域知识注入
"""
from typing import List, Dict, Any, Optional
from jinja2 import Template
from enum import Enum


class PromptStyle(Enum):
    """Prompt 风格"""
    STANDARD = "standard"       # 标准风格
    COT = "cot"                # 思维链风格
    FEW_SHOT = "few_shot"      # 少样本学习风格
    STRICT = "strict"          # 严格输出风格


class PromptTemplate:
    """Prompt 模板渲染器"""
    def __init__(self, template: str):
        self.template = Template(template)

    def render(self, **kwargs) -> str:
        return self.template.render(**kwargs)


# ============================================================================
# 系统 Prompt
# ============================================================================

AVIATION_DOMAIN_KNOWLEDGE = """
## 航空作动系统领域知识

### 关键术语
- 作动器（Actuator）：将能量转换为机械运动的装置
- 冗余（Redundancy）：备份系统，提高可靠性
- 电传（Fly-by-Wire）：电子飞行控制系统
- 适航（Airworthiness）：满足飞行安全标准的证明

### 审查要点
- 技术参数必须完整且准确
- 安全性分析必须符合适航规范
- 测试验证必须覆盖关键场景
- 文档结构必须清晰、逻辑连贯
"""

REVIEW_SYSTEM_PROMPT = """
你是一名航空作动系统领域的高级工程专家，熟悉适航规范、设计报告和工程文档审查标准。

{domain_knowledge}

## 审查原则
1. **专业性**：使用准确的术语，避免口语化
2. **可执行性**：给出具体、可操作的修改建议
3. **规范性**：严格遵循输出格式要求
4. **客观性**：基于规则进行客观判断

## 输出要求
- 严格按照指定的 JSON 格式输出
- 不要输出任何额外解释或多余内容
- 确保所有必需字段都存在
- 使用中文进行描述
"""


# ============================================================================
# Few-Shot 示例
# ============================================================================

FEW_SHOT_EXAMPLES = """
## 参考示例

### 示例 1：发现术语缺失
输入文本：
"该系统采用液压驱动方式，具有良好的响应特性。"

审查规则：
- 作动系统关键术语检查

审查结果：
{
    "passed": false,
    "issues": [
        {
            "rule_id": "actuator_keywords",
            "rule_name": "作动系统关键术语检查",
            "description": "缺少关键术语：作动器、冗余、电传",
            "severity": "warning",
            "suggestion": "建议补充关键术语以符合航空工程文档规范，例如明确'作动器类型'、'冗余设计'等内容"
        }
    ],
    "summary": "文档缺少航空作动系统的核心术语，需要补充相关技术描述"
}

### 示例 2：格式规范检查
输入文本：
"系统参数  如下  响应时间<100ms   工作温度-40~+60℃"

审查规则：
- 格式规范检查

审查结果：
{
    "passed": false,
    "issues": [
        {
            "rule_id": "format_check",
            "rule_name": "格式规范检查",
            "description": "文本中存在多余空格，格式不规范",
            "severity": "info",
            "suggestion": "建议删除多余空格，统一使用标准格式：'系统参数如下：响应时间 < 100 ms，工作温度 -40~+60℃'"
        }
    ],
    "summary": "格式不规范，存在多余空格和单位使用不统一的问题"
}

### 示例 3：通过审查
输入文本：
"该作动系统采用电液伺服控制，具有双冗余设计，响应时间为50ms，工作温度范围为-40℃至+60℃，符合RTCA/DO-160G标准要求。"

审查规则：
- 作动系统关键术语检查
- 格式规范检查

审查结果：
{
    "passed": true,
    "issues": [],
    "summary": "文档内容完整，术语使用准确，格式规范，符合审查要求"
}
"""


# ============================================================================
# 思维链 Prompt 模板
# ============================================================================

COT_REASONING_TEMPLATE = """
## 审查思维过程

请按照以下步骤进行审查：

### 第一步：理解规则
- 逐条阅读审查规则
- 明确每条规则的检查要点
- 确定违反规则的判定标准

### 第二步：分析文本
- 通读文档内容
- 识别关键信息和技术要素
- 标注可能的疑点

### 第三步：对照检查
- 逐条规则对照文本内容
- 记录发现的问题
- 评估问题严重程度

### 第四步：形成结论
- 汇总所有发现的问题
- 按严重程度排序
- 给出修改建议

现在开始审查：
"""


# ============================================================================
# 章节审查 Prompt
# ============================================================================

REVIEW_SECTION_PROMPT = """请审查以下文档片段：

【文档片段】
{{ section_text }}

【审查规则】
{% for rule in rules %}
{{ loop.index }}. **{{ rule.name }}**
   - 说明：{{ rule.description }}
{% endfor %}

【审查要求】
1. 逐条检查规则，判断文档片段是否符合要求
2. 识别存在的问题（如果有）
3. 评估问题严重程度（error/warning/info）
4. 提供具体可执行的修改建议

【输出格式】
请严格按照以下 JSON 格式输出：
```json
{
    "passed": true,
    "issues": [
        {
            "rule_id": "规则ID",
            "rule_name": "规则名称",
            "description": "问题描述",
            "severity": "error/warning/info",
            "suggestion": "修改建议"
        }
    ],
    "summary": "审查总结"
}
```

**注意事项：**
- `passed`：所有规则都通过则为 true，否则为 false
- `severity`：error（严重错误）、warning（警告）、info（信息提示）
- `issues`：按严重程度从高到低排序
- 如果没有问题，`issues` 数组为空

{few_shot_examples}

如果无法生成有效 JSON，请返回：
```json
{"error": "无法解析"}
```
"""

REVIEW_SECTION_PROMPT_COT = REVIEW_SECTION_PROMPT + """

{cot_reasoning}
"""


# ============================================================================
# 文档审查 Prompt
# ============================================================================

REVIEW_DOCUMENT_PROMPT = """请对以下文档进行全面审查：

【文档标题】
{{ document_title }}

【文档内容】
{{ document_content }}

【审查规则】
{% for rule in rules %}
{{ loop.index }}. **{{ rule.name }}**
   - 说明：{{ rule.description }}
{% endfor %}

【审查重点】
{% for focus in review_focus %}
- {{ focus }}
{% endfor %}

【审查维度】
1. **内容完整性**：是否覆盖关键要点
2. **格式规范性**：是否符合文档规范
3. **逻辑一致性**：是否前后连贯
4. **技术准确性**：技术参数是否准确
5. **标准符合性**：是否符合相关标准

【输出格式】
请严格按照以下 JSON 格式输出：
```json
{
    "summary": "总体评价（2-3句话概括文档质量）",
    "issues": [
        {
            "rule_id": "规则ID",
            "rule_name": "规则名称",
            "description": "问题描述",
            "severity": "error/warning/info",
            "suggestion": "修改建议",
            "location": "问题位置描述（可选）"
        }
    ],
    "suggestions": [
        "整体改进建议1",
        "整体改进建议2"
    ],
    "conclusion": "通过/不通过/需要修改",
    "score": 85
}
```

**字段说明：**
- `summary`：简洁的总体评价
- `issues`：按严重程度排序的问题列表
- `suggestions`：整体改进建议
- `conclusion`：最终结论（通过/不通过/需要修改）
- `score`：文档质量评分（0-100）

如果无法生成有效 JSON，请返回：
```json
{"error": "无法解析"}
```
"""

REVIEW_DOCUMENT_PROMPT_COT = REVIEW_DOCUMENT_PROMPT + """

{cot_reasoning}
"""


# ============================================================================
# 默认配置
# ============================================================================

DEFAULT_REVIEW_FOCUS = [
    "内容完整性（是否覆盖关键要点）",
    "格式规范性（是否符合文档规范）",
    "逻辑一致性（是否前后连贯）",
    "技术准确性（技术参数是否准确）",
    "标准符合性（是否符合行业标准）"
]


# ============================================================================
# Prompt 构建器
# ============================================================================

class ReviewPromptBuilder:
    """审查 Prompt 构建器 - 优化版本"""

    def __init__(
        self,
        style: PromptStyle = PromptStyle.STANDARD,
        enable_cot: bool = False,
        enable_few_shot: bool = True,
        enable_domain_knowledge: bool = True
    ):
        """
        初始化 Prompt 构建器

        Args:
            style: Prompt 风格
            enable_cot: 是否启用思维链
            enable_few_shot: 是否启用少样本示例
            enable_domain_knowledge: 是否注入领域知识
        """
        self.style = style
        self.enable_cot = enable_cot or style == PromptStyle.COT
        self.enable_few_shot = enable_few_shot or style == PromptStyle.FEW_SHOT
        self.enable_domain_knowledge = enable_domain_knowledge

        # 构建系统 Prompt
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建系统 Prompt"""
        domain_knowledge = AVIATION_DOMAIN_KNOWLEDGE if self.enable_domain_knowledge else ""
        return REVIEW_SYSTEM_PROMPT.format(domain_knowledge=domain_knowledge)

    def build_document_review_prompt(
        self,
        document_title: str,
        document_content: str,
        rules: List[Dict[str, str]],
        review_focus: List[str] = None
    ) -> str:
        """
        构建文档审查 Prompt

        Args:
            document_title: 文档标题
            document_content: 文档内容
            rules: 审查规则列表
            review_focus: 审查重点

        Returns:
            完整的 Prompt 字符串
        """
        focus = review_focus or DEFAULT_REVIEW_FOCUS

        # 选择 Prompt 模板
        if self.enable_cot:
            template_str = REVIEW_DOCUMENT_PROMPT_COT
        else:
            template_str = REVIEW_DOCUMENT_PROMPT

        # 准备模板变量
        cot_reasoning = COT_REASONING_TEMPLATE if self.enable_cot else ""

        template = PromptTemplate(template_str)
        return template.render(
            document_title=document_title,
            document_content=document_content,
            rules=rules,
            review_focus=focus,
            cot_reasoning=cot_reasoning
        )

    def build_section_review_prompt(
        self,
        section_text: str,
        rules: List[Dict[str, str]]
    ) -> str:
        """
        构建章节审查 Prompt

        Args:
            section_text: 章节文本
            rules: 审查规则列表

        Returns:
            完整的 Prompt 字符串
        """
        # 选择 Prompt 模板
        if self.enable_cot:
            template_str = REVIEW_SECTION_PROMPT_COT
        else:
            template_str = REVIEW_SECTION_PROMPT

        # 准备模板变量
        few_shot_examples = FEW_SHOT_EXAMPLES if self.enable_few_shot else ""
        cot_reasoning = COT_REASONING_TEMPLATE if self.enable_cot else ""

        template = PromptTemplate(template_str)
        return template.render(
            section_text=section_text,
            rules=rules,
            few_shot_examples=few_shot_examples,
            cot_reasoning=cot_reasoning
        )

    def get_system_prompt(self) -> str:
        """获取系统 Prompt"""
        return self.system_prompt


# ============================================================================
# Prompt 评估工具
# ============================================================================

class PromptEvaluator:
    """Prompt 效果评估器"""

    @staticmethod
    def evaluate_prompt_quality(prompt: str) -> Dict[str, Any]:
        """
        评估 Prompt 质量

        Args:
            prompt: 要评估的 Prompt

        Returns:
            质量评估结果
        """
        return {
            "length": len(prompt),
            "token_estimate": len(prompt.split()),
            "has_examples": "示例" in prompt or "example" in prompt.lower(),
            "has_json_format": "json" in prompt.lower(),
            "has_reasoning": "思维" in prompt or "reasoning" in prompt.lower(),
            "complexity": "高" if len(prompt) > 2000 else "中" if len(prompt) > 1000 else "低"
        }

    @staticmethod
    def compare_prompts(prompt1: str, prompt2: str) -> Dict[str, Any]:
        """
        比较两个 Prompt

        Args:
            prompt1: 第一个 Prompt
            prompt2: 第二个 Prompt

        Returns:
            比较结果
        """
        eval1 = PromptEvaluator.evaluate_prompt_quality(prompt1)
        eval2 = PromptEvaluator.evaluate_prompt_quality(prompt2)

        return {
            "prompt1": eval1,
            "prompt2": eval2,
            "length_diff": eval1["length"] - eval2["length"],
            "recommendation": "使用 Prompt 1" if eval1["has_examples"] else "使用 Prompt 2"
        }


# ============================================================================
# 动态 Prompt 构建器
# ============================================================================

class DynamicPromptBuilder:
    """动态 Prompt 构建器 - 根据场景调整 Prompt"""

    @staticmethod
    def build_prompt_by_document_type(
        doc_type: str,
        content: str,
        rules: List[Dict[str, str]]
    ) -> str:
        """
        根据文档类型构建专用 Prompt

        Args:
            doc_type: 文档类型（design_report/test_report/etc）
            content: 文档内容
            rules: 审查规则

        Returns:
            定制的 Prompt
        """
        doc_type_prompts = {
            "design_report": {
                "focus": ["设计完整性", "安全性分析", "符合适航规范"],
                "system_addition": "\n## 设计报告审查要点\n- 需求覆盖度\n- 设计验证方法\n- 安全性评估"
            },
            "test_report": {
                "focus": ["测试覆盖度", "测试方法有效性", "结果准确性"],
                "system_addition": "\n## 测试报告审查要点\n- 测试用例完整性\n- 测试条件设置\n- 结果分析方法"
            },
            "maintenance_manual": {
                "focus": ["操作清晰性", "安全性提示", "故障诊断方法"],
                "system_addition": "\n## 维护手册审查要点\n- 操作步骤明确性\n- 安全警示标识\n- 故障排查逻辑"
            }
        }

        config = doc_type_prompts.get(doc_type, doc_type_prompts["design_report"])

        builder = ReviewPromptBuilder(
            style=PromptStyle.FEW_SHOT,
            enable_cot=True
        )

        return builder.build_document_review_prompt(
            document_title=f"{doc_type}审查",
            document_content=content,
            rules=rules,
            review_focus=config["focus"]
        )

    @staticmethod
    def build_strict_prompt(
        section_text: str,
        rules: List[Dict[str, str]]
    ) -> str:
        """
        构建严格审查 Prompt（用于关键文档）

        Args:
            section_text: 章节文本
            rules: 审查规则

        Returns:
            严格审查 Prompt
        """
        strict_rules = [
            {"name": r["name"] + "（严格）", "description": r["description"] + " - 必须严格满足，不得有任何例外"}
            for r in rules
        ]

        builder = ReviewPromptBuilder(
            style=PromptStyle.STRICT,
            enable_cot=True,
            enable_few_shot=True
        )

        return builder.build_section_review_prompt(section_text, strict_rules)
