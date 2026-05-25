# Web界面设计文档

## 项目信息

**项目名称：** 航空作动产品技术文档审查与生成平台 Web界面

**创建日期：** 2025-05-25

**文档版本：** 1.0

---

## 1. 项目概述

### 1.1 目标

为现有的航空作动产品技术文档审查与生成平台添加Web界面，提升易用性和用户体验。

### 1.2 目标用户

- **文档审查人员**：使用审查功能，上传文档、查看审查报告
- **文档编写人员**：使用生成功能，根据需求生成技术文档
- **项目经理**：查看审查进度、历史记录、统计分析

### 1.3 使用规模

10-50人中小型团队，需要基本的并发支持。

### 1.4 核心功能

- 文档上传与审查
- 文档生成（基于现有模板）
- 审查历史管理
- 规则管理
- 统计分析

---

## 2. 界面设计

### 2.1 整体布局

**选择方案：侧边栏布局**

```
┌────────────┬──────────────────────────────┐
│            │                              │
│  侧边栏导航 │       主内容区域              │
│            │                              │
│  - 首页    │                              │
│  - 审查    │      (动态内容)               │
│  - 生成    │                              │
│  - 历史    │                              │
│  - 规则    │                              │
│  - 统计    │                              │
│            │                              │
└────────────┴──────────────────────────────┘
```

**选择理由：**
- 功能模块清晰，便于多角色用户快速找到所需功能
- 易于后续扩展新功能
- 符合后台管理系统的用户习惯

### 2.2 首页设计

**设计方案：混合首页（快捷操作 + 数据概览）**

**上半部分 - 快捷操作：**
- 4个大尺寸快捷操作卡片
- 每个卡片包含：图标、标题、描述、左侧彩色边框
  - 📄 上传文档审查（蓝色）
  - ✨ 生成新文档（绿色）
  - 📋 查看历史（橙色）
  - ⚙️ 规则管理（紫色）

**下半部分 - 数据概览：**
- 4个核心指标卡片
- 显示：待审查(12)、审查中(5)、已完成(48)、通过率(89%)
- 数字放大突出显示

### 2.3 文档审查页面

**页面流程：**

1. **上传文档**
   - 拖拽上传区域
   - 支持DOCX格式
   - 文件大小限制50MB

2. **审查配置**
   - 审查模式选择：规则+LLM / 仅规则 / 仅LLM
   - 规则集选择：航空作动系统

3. **开始审查**
   - 提交按钮触发审查
   - 后台异步执行

4. **审查进度**
   - 实时显示章节进度（如：3/5章节）
   - 进度条可视化

5. **审查报告**
   - 问题列表（按严重程度排序）
   - 章节级别结果
   - 修改建议
   - 导出DOCX/PDF

### 2.4 文档生成页面

**页面流程：**

1. **选择文档类型**
   - 📋 设计报告 - 设计报告模板.dotx
   - 🧪 测试报告 - 测试报告模板.dotx
   - 🔧 维护手册 - 维护手册模板.dotx
   - 📊 分析报告 - 分析报告模板.dotx

2. **查看模板信息**
   - 模板文件名
   - 章节结构预览

3. **输入需求信息**
   - 文档标题
   - 产品描述（多行文本）
   - 关键技术参数
   - 参考文档上传（可选）

4. **生成选项**
   - 按照模板章节结构生成
   - 参考历史类似文档内容
   - 保留模板格式和样式

5. **开始生成**
   - LLM基于模板结构生成各章节内容
   - 显示生成进度

6. **预览导出**
   - 在线预览生成的文档
   - 编辑和调整
   - 导出为DOCX格式

---

## 3. 技术架构

### 3.1 技术栈

**选择方案：Flask + Bootstrap**

| 组件 | 技术选择 |
|------|----------|
| 后端框架 | Flask |
| 前端框架 | Bootstrap 5 + Jinja2模板 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产）|
| 任务队列 | Celery + Redis |
| WebSocket | Flask-SocketIO |
| 文件存储 | 本地文件系统 / MinIO |

**选择理由：**
- 现有代码都是Python，无需额外技术栈
- 轻量级部署，适合10-50人规模
- 开发快速，易于维护
- Bootstrap组件丰富，界面美观

### 3.2 项目结构

```
new-wdsc/
├── web/                        # 新增Web模块
│   ├── __init__.py
│   ├── app.py                  # Flask应用入口
│   ├── config.py               # Web配置
│   ├── routes/                 # 路由模块
│   │   ├── __init__.py
│   │   ├── index.py            # 首页路由
│   │   ├── review.py           # 审查路由
│   │   ├── generate.py         # 生成路由
│   │   ├── history.py          # 历史记录路由
│   │   ├── rules.py            # 规则管理路由
│   │   └── api.py              # API接口
│   ├── templates/              # Jinja2模板
│   │   ├── base.html           # 基础模板
│   │   ├── index.html          # 首页
│   │   ├── review.html         # 审查页面
│   │   ├── generate.html       # 生成页面
│   │   ├── history.html        # 历史页面
│   │   ├── rules.html          # 规则管理页面
│   │   └── stats.html          # 统计页面
│   ├── static/                 # 静态资源
│   │   ├── css/
│   │   │   └── custom.css      # 自定义样式
│   │   ├── js/
│   │   │   └── main.js         # 主要JavaScript
│   │   └── img/
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   ├── document.py         # 文档模型
│   │   ├── task.py             # 任务模型
│   │   ├── template.py         # 模板模型
│   │   └── user.py             # 用户模型
│   ├── tasks/                  # 异步任务
│   │   ├── __init__.py
│   │   ├── review_tasks.py     # 审查任务
│   │   └── generate_tasks.py   # 生成任务
│   └── utils/                  # 工具函数
│       ├── __init__.py
│       ├── auth.py             # 认证工具
│       └── upload.py           # 上传工具
├── core/                       # 现有核心模块
├── llm/                        # 现有LLM模块
├── rules/                      # 现有规则模块
└── ...
```

### 3.3 核心模块设计

#### 3.3.1 Flask应用初始化

```python
# web/app.py
from flask import Flask, render_template
from flask_socketio import SocketIO
from config.settings import settings

app = Flask(__name__)
app.config['SECRET_KEY'] = settings.secret_key
app.config['UPLOAD_FOLDER'] = settings.upload_folder
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

socketio = SocketIO(app, cors_allowed_origins="*")

from web.routes import *
from web.tasks import *

if __name__ == '__main__':
    socketio.run(app, debug=settings.is_dev, host='0.0.0.0', port=5000)
```

#### 3.3.2 路由模块

```python
# web/routes/review.py
from flask import Blueprint, request, jsonify, render_template
from web.tasks.review_tasks import start_review_task
import os

bp = Blueprint('review', __name__)

@bp.route('/review')
def review_page():
    return render_template('review.html')

@bp.route('/api/review/start', methods=['POST'])
def start_review():
    file = request.files['document']
    mode = request.form.get('mode', 'both')

    # 保存文件
    filepath = save_uploaded_file(file)

    # 启动异步审查任务
    task = start_review_task.delay(filepath, mode)

    return jsonify({'task_id': task.id})

@bp.route('/api/review/status/<task_id>')
def review_status(task_id):
    from celery.result import AsyncResult
    task = AsyncResult(task_id)
    return jsonify({'status': task.status, 'result': task.result})
```

#### 3.3.3 异步任务

```python
# web/tasks/review_tasks.py
from celery import Celery
from core.executor import ReviewExecutor
from rules.loaders.rule_loader import RuleLoader
from llm.client import LLMClientFactory

celery_app = Celery('tasks', broker='redis://localhost:6379/0')

@celery_app.task
def start_review_task(filepath, mode):
    # 初始化审查执行器
    rules = RuleLoader.load_all_rules(profile="aviation")
    llm_client = LLMClientFactory.create_client("siliconflow")
    executor = ReviewExecutor(rules, llm_client, use_llm=(mode != 'rule_only'))

    # 解析文档
    from parsers.docx_parser import ParserFactory
    parser = ParserFactory.get_parser(".docx")
    document = parser.parse(filepath)

    # 执行审查
    result = executor.review_document(document)

    return {
        'passed': result.overall_passed,
        'total_issues': result.total_issues,
        'errors': result.errors,
        'warnings': result.warnings
    }
```

---

## 4. 数据模型

### 4.1 核心数据表

#### documents（文档表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| filename | String(255) | 文件名 |
| filepath | String(500) | 文件路径 |
| file_type | String(50) | 文件类型（review/generate） |
| file_size | Integer | 文件大小（字节） |
| status | String(20) | 状态（pending/processing/completed/failed） |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

#### review_tasks（审查任务表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| document_id | Integer | 文档ID（外键） |
| task_id | String(255) | Celery任务ID |
| mode | String(20) | 审查模式（rule/llm/both） |
| status | String(20) | 状态（pending/processing/completed/failed） |
| result | JSON | 审查结果 |
| created_at | DateTime | 创建时间 |
| completed_at | DateTime | 完成时间 |

#### generate_tasks（生成任务表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| template_id | Integer | 模板ID（外键） |
| task_id | String(255) | Celery任务ID |
| params | JSON | 生成参数 |
| status | String(20) | 状态 |
| result | JSON | 生成结果 |
| output_path | String(500) | 输出文件路径 |
| created_at | DateTime | 创建时间 |
| completed_at | DateTime | 完成时间 |

#### templates（模板表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| name | String(255) | 模板名称 |
| type | String(50) | 文档类型（design_report/test_report/etc） |
| filepath | String(500) | 模板文件路径 |
| structure | JSON | 章节结构定义 |
| enabled | Boolean | 是否启用 |
| created_at | DateTime | 创建时间 |

#### review_history（审查历史表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| document_id | Integer | 文档ID（外键） |
| task_id | Integer | 任务ID（外键） |
| version | Integer | 版本号 |
| created_at | DateTime | 创建时间 |

---

## 5. 接口设计

### 5.1 审查接口

```
POST /api/review/start
- 上传文档并启动审查
- 请求：multipart/form-data（document, mode）
- 响应：{"task_id": "xxx"}

GET /api/review/status/<task_id>
- 查询审查状态
- 响应：{"status": "processing", "progress": 60}

GET /api/review/result/<task_id>
- 获取审查结果
- 响应：{审查结果JSON}
```

### 5.2 生成接口

```
POST /api/generate/start
- 启动文档生成
- 请求：JSON（template_id, title, description, params）
- 响应：{"task_id": "xxx"}

GET /api/generate/status/<task_id>
- 查询生成状态
- 响应：{"status": "processing", "current_section": "4. 安全性分析"}

GET /api/generate/download/<task_id>
- 下载生成的文档
- 响应：文件流
```

### 5.3 WebSocket接口

```
连接：ws://localhost:5000/ws/review/<task_id>
- 实时推送审查进度
- 事件：{"type": "progress", "data": {"current": 3, "total": 5, "section": "4. 安全性分析"}}
```

---

## 6. 部署方案

### 6.1 开发环境

```bash
# 安装依赖
pip install flask flask-socketio celery redis

# 启动Redis
redis-server

# 启动Celery Worker
celery -A web.tasks.celery_app worker --loglevel=info

# 启动Flask应用
python web/app.py
```

### 6.2 生产环境

**使用Docker容器化部署：**

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--worker-class", "socketio.worker.GeventWebWorker", "--bind", "0.0.0.0:5000", "web.app:app"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "5000:5000"
    depends_on:
      - redis
      - postgres
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/docdb
      - REDIS_URL=redis://redis:6379/0

  celery:
    build: .
    command: celery -A web.tasks.celery_app worker --loglevel=info
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=docdb
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## 7. 实施计划

| 阶段 | 内容 | 工作量 |
|------|------|--------|
| 第1周 | Flask应用框架搭建、基础页面、数据库模型 | 5天 |
| 第2周 | 文档审查功能集成、异步任务、进度显示 | 5天 |
| 第3周 | 文档生成功能集成、模板管理 | 5天 |
| 第4周 | 审查历史页面、历史记录查询、对比功能 | 5天 |
| 第5周 | 规则管理页面、统计分析页面、数据可视化 | 5天 |
| 第6周 | 测试、优化、部署文档、用户培训 | 5天 |

**总计：6周（30个工作日）**

---

## 8. 风险与注意事项

### 8.1 技术风险

1. **文件上传安全性**
   - 需要验证文件类型和内容
   - 限制文件大小
   - 防止恶意文件上传

2. **并发处理**
   - Celery任务队列需要合理配置worker数量
   - Redis需要持久化配置防止任务丢失

3. **大文件处理**
   - DOCX文件可能较大，需要分块处理
   - 内存管理需要优化

### 8.2 用户体验风险

1. **审查/生成时间较长**
   - 需要清晰的进度反馈
   - 考虑添加预估完成时间

2. **结果准确性**
   - LLM生成结果可能需要人工审核
   - 需要提供编辑功能

### 8.3 数据安全风险

1. **文档存储**
   - 敏感文档需要加密存储
   - 定期备份

2. **访问控制**
   - 需要实现用户认证和权限管理
   - 不同角色看到不同内容

---

## 9. 后续优化方向

1. **用户权限管理** - 实现基于角色的访问控制
2. **知识库集成** - 基于历史文档的智能检索
3. **协作功能** - 文档评论、审批流程
4. **多语言支持** - 中英文界面切换
5. **移动端适配** - 响应式设计优化
6. **性能优化** - 缓存策略、数据库优化
