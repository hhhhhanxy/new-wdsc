# 航空作动产品文档智能化审查框架

## 项目简介

本项目旨在构建面向航空作动产品的智能化文档处理平台，重点突破多格式文档结构化解析、文档辅助生成与合规智能审查等关键技术，实现文档内容智能提取、规范自动校验与辅助编制。

## 核心功能

1. **多格式文档解析模块**：支持Word、PDF等文档的统一解析与结构化处理
2. **文档辅助生成模块**：基于模板和知识库实现文档内容的智能填充
3. **文档智能审查模块**：自动开展格式规范检查、内容完整性校验、工程术语一致性分析及合规性验证

## 技术栈

- Python 3.8+
- Flask (Web服务)
- spaCy (自然语言处理)
- PyPDF2 (PDF解析)
- python-docx (Word文档处理)
- NetworkX (知识图谱)
- scikit-learn (机器学习)

## 项目结构

```
wdsc/
├── app/
│   ├── __init__.py
│   ├── modules/
│   │   ├── document_parser.py      # 文档解析模块
│   │   ├── document_generator.py   # 文档生成模块
│   │   └── document_reviewer.py    # 文档审查模块
│   ├── services/
│   │   ├── nlp_service.py          # 自然语言处理服务
│   │   └── knowledge_base.py       # 知识库服务
│   └── utils/
│       ├── config.py               # 配置文件
│       └── helpers.py              # 工具函数
├── data/
│   ├── templates/                  # 文档模板
│   ├── knowledge/                  # 领域知识
│   └── rules/                      # 审查规则
├── main.py                         # 主入口
├── requirements.txt                # 依赖包
└── README.md                       # 项目说明
```

## 快速开始

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 启动服务
```bash
python main.py
```

3. 访问API
```
http://localhost:5000/api/docs
```