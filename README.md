# 文档审查智能体

一个基于大模型和规则的文档审查工具，用于自动检查DOCX文档的质量和合规性。

# 项目目标
这是一个“文档审查智能体”，用于对工程文档（尤其是航空作动领域）进行自动审查，包含：
1. 规则引擎（Rule-based）
2. LLM审查（大模型）
3. 报告生成（txt/md/json/docx）


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
- main.py：程序入口
- core/executor.py：审查执行核心（规则 + LLM）
- rules/：规则系统（base_rule、checkers、grammar等）
- llm/client.py：LLM调用
- llm/prompts.py：Prompt构建 & 输出解析
- reporters/base_reporter.py：报告生成
