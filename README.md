# 文档审查智能体

一个基于大模型和规则的文档审查工具，用于自动检查DOCX文档的质量和合规性。

# 项目目标
这是一个“文档审查智能体”，用于对工程文档（尤其是航空作动领域）进行自动审查，包含：
1. 规则引擎（Rule-based）
2. LLM审查（大模型）
3. 报告生成（txt/md/json/docx）


## 项目结构
new-wdsc/
├── config/                   # 配置模块
│   ├── __init__.py
│   └── settings.py           # 项目配置文件
├── core/                     # 核心模块
│   ├── __init__.py
│   └── executor.py           # 文档审查执行器，处理文档、规则、LLM调用
├── llm/                      # 大语言模型模块
│   ├── __init__.py
│   ├── client.py             # LLM客户端实现
│   └── prompts.py            # Prompt构建器
├── models/                   # 数据模型
│   ├── __init__.py
│   └── document.py           # 文档模型定义
├── parsers/                  # 文档解析器
│   ├── __init__.py
│   ├── docx_parser.py        # DOCX文档解析器
│   └── review_parser.py      # 审查结果解析器
├── reporters/                # 报告生成器
│   ├── __init__.py
│   └── base_reporter.py      # 报告基类和具体实现
├── rules/                    # 规则系统
│   ├── aviation/             # 航空行业规则
│   │   ├── __init__.py
│   │   └── actuator_rules.py # 作动系统规则
│   ├── common/               # 通用规则
│   │   ├── __init__.py
│   │   ├── format.py         # 格式规则
│   │   └── grammar.py        # 语法规则
│   ├── loaders/              # 规则加载器
│   │   ├── __init__.py
│   │   └── rule_loader.py    # 规则加载器：加载通用规则+行业规则
│   ├── __init__.py
│   ├── base_rule.py          # 规则基类
│   └── checkers.py           # 规则检查器
├── .env                      # 环境变量配置
├── .gitignore                # Git忽略文件
├── .python-version           # Python版本配置
├── README.md                 # 项目说明文档
├── __init__.py
├── document.docx             # 示例文档
├── document_report.docx      # 示例报告
├── main.py                   # 项目入口
├── pyproject.toml            # 项目依赖配置
└── uv.lock                   # 依赖版本锁定文件


## 核心模块说明
- main.py：程序入口
- core/executor.py：审查执行核心（规则 + LLM）
- rules/：规则系统（base_rule、checkers、grammar等）
- llm/client.py：LLM调用
- llm/prompts.py：Prompt构建 & 输出解析
- reporters/base_reporter.py：报告生成
