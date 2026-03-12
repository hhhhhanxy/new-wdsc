# 文档审查智能体

一个基于大模型和规则的文档审查工具，用于自动检查DOCX文档的质量和合规性。

## 项目结构

```
profileRe/
├── config/                 # 配置模块
│   ├── __init__.py
│   └── settings.py        # 配置管理
├── models/                 # 数据模型
│   ├── __init__.py
│   └── document.py        # 文档模型定义
├── parsers/               # 文档解析器
│   ├── __init__.py
│   └── docx_parser.py     # DOCX解析器
├── rules/                 # 规则引擎
│   ├── __init__.py
│   ├── base_rule.py       # 规则基类和注册表
│   └── checkers.py        # 内置规则检查器
├── llm/                   # 大模型接口
│   ├── __init__.py
│   ├── client.py          # LLM客户端
│   └── prompts.py         # 提示词模板
├── core/                  # 核心执行器
│   ├── __init__.py
│   └── executor.py        # 审查执行器
├── reporters/             # 报告生成器
│   ├── __init__.py
│   └── base_reporter.py   # 多格式报告生成
├── main.py                # 主程序入口
├── __init__.py
├── requirements.txt       # 依赖包
├── .env.example          # 环境变量示例
├── .gitignore
├── .python-version
└── pyproject.toml
```

## 核心模块说明

| 模块 | 功能 |
|------|------|
| **config** | 管理项目配置，包括LLM API密钥、模型设置等 |
| **models** | 定义文档数据结构，包括文档节、解析结果等 |
| **parsers** | 解析DOCX文档，提取段落、标题、表格等内容 |
| **rules** | 规则引擎，支持自定义规则、规则注册、启用/禁用 |
| **llm** | LLM客户端封装，支持OpenAI兼容API，内置审查提示词 |
| **core** | 审查执行器，协调规则检查和LLM审查 |
| **reporters** | 生成TXT/Markdown/JSON格式报告 |

## 安装方法

1. **克隆项目**
```bash
git clone <repository-url>
cd profileRe
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
cp .env.example .env
# 编辑.env文件，填入LLM API密钥
```

## 使用方法

### 命令行使用

```bash
# 基本使用 - 生成Markdown报告
python main.py document.docx

# 指定输出路径和格式
python main.py document.docx -o review_report.md -f md

# 仅使用规则审查（不调用LLM）
python main.py document.docx --no-llm

# 使用JSON格式输出
python main.py document.docx -f json
```

### 代码中使用

```python
from main import DocumentReviewer
from rules.base_rule import Rule, RuleCategory, RuleSeverity

# 初始化审查器
reviewer = DocumentReviewer(use_llm=True)

# 添加自定义规则
def custom_check(section, context):
    # 自定义检查逻辑
    pass

custom_rule = Rule(
    rule_id="custom_001",
    name="自定义检查",
    description="检查特定内容",
    category=RuleCategory.CUSTOM,
    severity=RuleSeverity.WARNING,
    check_func=custom_check
)
reviewer.add_rule(custom_rule)

# 执行审查
result = reviewer.review("document.docx")

# 打印结果摘要
reviewer.print_summary(result)

# 生成报告
reviewer.generate_report(result, "report.md", "md")
```

## 内置规则

- **标题格式检查**：检查标题是否包含编号
- **段落长度检查**：检查段落是否过长
- **可扩展**：可添加更多自定义规则

## 扩展方式

- **添加新规则**：继承 `BaseRuleChecker` 或直接定义检查函数
- **支持新文档格式**：继承 `BaseParser` 并注册到 `ParserFactory`
- **添加新LLM提供商**：继承 `BaseLLMClient` 并注册到 `LLMClientFactory`
- **添加新报告格式**：继承 `BaseReporter` 并注册到 `ReporterFactory`

## 报告格式

支持三种报告格式：
- **TXT**：纯文本格式，适合快速查看
- **Markdown**：结构化格式，适合阅读和分享
- **JSON**：机器可读格式，适合后续处理

## 注意事项

- 使用LLM功能时需要配置有效的API密钥
- 大型文档可能会消耗较多的LLM token
- 可以通过 `--no-llm` 参数禁用LLM功能，仅使用规则检查