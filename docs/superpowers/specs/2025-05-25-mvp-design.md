# Web界面设计文档 - MVP版本

## 项目信息

**项目名称：** 航空作动产品技术文档审查与生成平台 Web界面

**创建日期：** 2025-05-25

**文档版本：** 1.0 (MVP)

**截止日期：** 2025年6月30日（35天）

---

## 1. 项目概述

### 1.1 目标

在35天内交付一个**最简化但可运行**的文档审查与生成平台Web界面。

### 1.2 策略

采用**MVP（最小可行产品）**策略，聚焦核心功能，砍掉所有非必要特性。

### 1.3 核心功能（仅保留）

- **文档审查**：上传DOCX → 审查 → 查看报告 → 下载报告
- **文档生成**：选择模板 → 输入信息 → 生成 → 下载
- **简单Web界面**：首页、审查页面、生成页面

### 1.4 不包含的功能（后续版本）

- ~~用户登录/权限系统~~
- ~~审查历史对比~~
- ~~复杂统计分析~~
- ~~规则管理界面~~
- ~~WebSocket实时进度~~（用轮询代替）
- ~~Docker部署~~（本地运行即可）

---

## 2. 界面设计

### 2.1 整体布局

**侧边栏布局（简化版）**

```
┌────────────┬──────────────────────────────┐
│            │                              │
│  侧边栏    │       主内容区域              │
│            │                              │
│  首页      │                              │
│  审查      │      (动态内容)               │
│  生成      │                              │
│            │                              │
└────────────┴──────────────────────────────┘
```

### 2.2 首页设计

**快捷操作 + 数据概览**

- 4个快捷操作卡片（突出显示）
- 4个核心指标（简洁展示）

### 2.3 审查页面

**简化流程：**

1. 上传DOCX文档（拖拽或点击）
2. 选择审查模式（默认：规则+LLM）
3. 点击"开始审查"
4. 显示进度（轮询更新）
5. 完成后显示报告
6. 下载报告（DOCX格式）

### 2.4 生成页面

**简化流程：**

1. 选择文档类型（4种）
2. 显示对应模板信息
3. 输入基本信息（标题、描述）
4. 点击"开始生成"
5. 显示进度（轮询更新）
6. 完成后下载文档（DOCX格式）

---

## 3. 技术架构

### 3.1 技术栈（最简化）

| 组件 | 技术选择 | 说明 |
|------|----------|------|
| 后端 | Flask | 轻量级Web框架 |
| 前端 | Bootstrap 5 | UI框架 |
| 模板引擎 | Jinja2 | Flask默认 |
| 数据库 | SQLite | 无需额外安装 |
| 异步任务 | threading.Thread | 后台线程 |
| 进度更新 | 轮询 | 每2秒查询一次 |
| 文件存储 | 本地文件系统 | upload文件夹 |

### 3.2 项目结构（简化）

```
new-wdsc/
├── web/                        # 新增Web模块
│   ├── app.py                  # Flask应用入口
│   ├── routes/                 # 路由模块
│   │   ├── __init__.py
│   │   ├── index.py            # 首页路由
│   │   ├── review.py           # 审查路由
│   │   └── generate.py         # 生成路由
│   ├── templates/              # Jinja2模板
│   │   ├── base.html           # 基础模板
│   │   ├── index.html          # 首页
│   │   ├── review.html         # 审查页面
│   │   └── generate.html       # 生成页面
│   ├── static/                 # 静态资源
│   │   ├── css/
│   │   │   └── custom.css      # 自定义样式
│   │   └── js/
│   │       └── main.js         # 主要JavaScript
│   ├── models.py               # 简化数据模型
│   └── tasks.py                # 后台任务（线程）
├── core/                       # 现有模块
├── llm/                        # 现有模块
├── rules/                      # 现有模块
├── parsers/                    # 现有模块
├── reporters/                  # 现有模块
├── run.py                      # 启动脚本
└── uploads/                    # 上传文件目录
```

---

## 4. 数据模型（简化）

### 4.1 数据表

```python
# web/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json
import sqlite3

class Database:
    def __init__(self, db_path='web/database.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.init_db()
    
    def init_db(self):
        cursor = self.conn.cursor()
        
        # 审查任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        
        # 生成任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generate_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type TEXT NOT NULL,
                template_name TEXT NOT NULL,
                params TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                result_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        
        self.conn.commit()
```

---

## 5. 核心模块设计

### 5.1 Flask应用初始化

```python
# web/app.py
from flask import Flask, render_template
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), '..', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

from web.routes import *
from web.models import Database

# 初始化数据库
db = Database()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

### 5.2 审查路由

```python
# web/routes/review.py
from flask import Blueprint, request, jsonify, render_template, current_app
import os
import threading
from datetime import datetime
from web.tasks import run_review_task
from web.models import Database

bp = Blueprint('review', __name__)

@bp.route('/review')
def review_page():
    return render_template('review.html')

@bp.route('/api/review/start', methods=['POST'])
def start_review():
    if 'document' not in request.files:
        return jsonify({'error': '请上传文档'}), 400
    
    file = request.files['document']
    if file.filename == '':
        return jsonify({'error': '请选择文件'}), 400
    
    if not file.filename.endswith('.docx'):
        return jsonify({'error': '只支持DOCX格式'}), 400
    
    # 保存文件
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # 创建任务记录
    db = request.environ.get('db')
    cursor = db.conn.cursor()
    cursor.execute('''
        INSERT INTO review_tasks (filename, filepath, mode, status)
        VALUES (?, ?, ?, ?)
    ''', (file.filename, filepath, 'both', 'pending'))
    db.conn.commit()
    task_id = cursor.lastrowid
    
    # 启动后台线程执行审查
    thread = threading.Thread(
        target=run_review_task,
        args=(task_id, filepath, 'both', db)
    )
    thread.start()
    
    return jsonify({'task_id': task_id})

@bp.route('/api/review/status/<int:task_id>')
def review_status(task_id):
    db = request.environ.get('db')
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT status, progress, result
        FROM review_tasks
        WHERE id = ?
    ''', (task_id,))
    
    row = cursor.fetchone()
    if row:
        status, progress, result = row
        return jsonify({
            'status': status,
            'progress': progress,
            'result': json.loads(result) if result else None
        })
    
    return jsonify({'error': '任务不存在'}), 404
```

### 5.3 后台任务

```python
# web/tasks.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.executor import ReviewExecutor
from rules.loaders.rule_loader import RuleLoader
from llm.client import LLMClientFactory
from parsers.docx_parser import ParserFactory
import json

def update_task_progress(db, task_id, progress, status=None):
    """更新任务进度"""
    cursor = db.conn.cursor()
    if status:
        cursor.execute('''
            UPDATE review_tasks SET progress = ?, status = ?
            WHERE id = ?
        ''', (progress, status, task_id))
    else:
        cursor.execute('''
            UPDATE review_tasks SET progress = ?
            WHERE id = ?
        ''', (progress, task_id))
    db.conn.commit()

def run_review_task(task_id, filepath, mode, db):
    """执行审查任务"""
    try:
        # 更新状态为处理中
        update_task_progress(db, task_id, 0, 'processing')
        
        # 初始化组件
        rules = RuleLoader.load_all_rules(profile="aviation")
        llm_client = LLMClientFactory.create_client("siliconflow")
        executor = ReviewExecutor(rules, llm_client, use_llm=(mode != 'rule_only'))
        
        # 解析文档
        update_task_progress(db, task_id, 10)
        parser = ParserFactory.get_parser(".docx")
        document = parser.parse(filepath)
        
        # 执行审查
        update_task_progress(db, task_id, 50)
        result = executor.review_document(document)
        
        # 保存结果
        update_task_progress(db, task_id, 90)
        result_data = {
            'passed': result.overall_passed,
            'total_issues': result.total_issues,
            'errors': result.errors,
            'warnings': result.warnings,
            'summary': result.summary
        }
        
        cursor = db.conn.cursor()
        cursor.execute('''
            UPDATE review_tasks
            SET result = ?, status = ?, progress = 100, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (json.dumps(result_data), 'completed', task_id))
        db.conn.commit()
        
    except Exception as e:
        update_task_progress(db, task_id, 0, 'failed')
        print(f"审查任务失败: {str(e)}")
```

---

## 6. 接口设计

### 6.1 审查接口

```
POST /api/review/start
- 启动审查任务
- 参数：multipart/form-data (document, mode)
- 响应：{"task_id": 123}

GET /api/review/status/<task_id>
- 查询任务状态
- 响应：{
    "status": "processing",
    "progress": 50,
    "result": null 或 {...}
  }
```

### 6.2 生成接口

```
POST /api/generate/start
- 启动生成任务
- 参数：JSON {
    "doc_type": "design_report",
    "title": "文档标题",
    "description": "产品描述"
  }
- 响应：{"task_id": 456}

GET /api/generate/status/<task_id>
- 查询生成状态
- 响应：{
    "status": "processing",
    "progress": 75,
    "result_path": null 或 "path/to/file.docx"
  }
```

---

## 7. Prompt与文档类型映射

### 7.1 配置结构

```python
# llm/prompts.py
DOCUMENT_TYPE_CONFIG = {
    "design_report": {
        "review_focus": [
            "设计完整性",
            "安全性分析",
            "符合适航规范"
        ]
    },
    "test_report": {
        "review_focus": [
            "测试覆盖度",
            "测试方法有效性"
        ]
    },
    "maintenance_manual": {
        "review_focus": [
            "操作清晰性",
            "安全警示"
        ]
    },
    "analysis_report": {
        "review_focus": [
            "分析方法",
            "数据支撑"
        ]
    }
}
```

### 7.2 使用方式

```python
# 在审查任务中
config = DOCUMENT_TYPE_CONFIG.get(doc_type, DOCUMENT_TYPE_CONFIG["design_report"])
review_focus = config["review_focus"]

# 使用对应的review_focus构建prompt
prompt = prompt_builder.build_document_review_prompt(
    document.title,
    document.raw_text[:5000],
    rules_info,
    review_focus=review_focus
)
```

---

## 8. 前端轮询示例

```javascript
// static/js/main.js
function pollReviewStatus(task_id) {
    const interval = setInterval(async () => {
        const response = await fetch(`/api/review/status/${task_id}`);
        const data = await response.json();
        
        // 更新进度条
        updateProgress(data.progress);
        
        // 检查是否完成
        if (data.status === 'completed') {
            clearInterval(interval);
            showResult(data.result);
        } else if (data.status === 'failed') {
            clearInterval(interval);
            showError('审查失败');
        }
    }, 2000); // 每2秒轮询一次
}
```

---

## 9. 实施计划

### 第1周（5月25-31日）：Flask应用框架

- [ ] Flask应用初始化
- [ ] 基础页面模板
- [ ] 侧边栏导航
- [ ] SQLite数据库初始化
- [ ] 文件上传功能
- [ ] 静态资源加载

**交付物：** 可运行的Flask应用，3个基础页面

### 第2周（6月1-7日）：文档审查功能

- [ ] 审查页面UI完善
- [ ] 集成现有审查模块
- [ ] 后台线程任务
- [ ] 审查报告展示
- [ ] 报告下载功能
- [ ] 轮询显示进度

**交付物：** 完整的文档审查功能

### 第3周（6月8-14日）：文档生成功能

- [ ] 生成页面UI完善
- [ ] 模板配置（代码）
- [ ] 集成LLM生成
- [ ] 生成结果展示
- [ ] 文档下载功能

**交付物：** 完整的文档生成功能

### 第4周（6月15-21日）：完善与集成

- [ ] Prompt与文档类型映射
- [ ] 首页数据统计
- [ ] 错误处理
- [ ] 界面优化
- [ ] 响应式适配

**交付物：** 完整集成的Web应用

### 第5周（6月22-30日）：测试与交付

- [ ] 端到端测试
- [ ] Bug修复
- [ ] 用户文档
- [ ] 启动脚本
- [ ] 部署交付

**交付物：** 可运行的MVP平台

---

## 10. 快速启动

```bash
# 安装依赖
pip install flask python-docx openai pydantic pydantic-settings jinja2 rich

# 启动应用
python run.py

# 访问
http://localhost:5000
```

---

## 11. 风险与注意事项

1. **时间紧张** - 35天时间有限，需要聚焦核心功能
2. **LLM稳定性** - 需要处理API调用失败的情况
3. **文件大小** - 大文档可能导致处理时间过长
4. **并发处理** - 多用户同时使用时的线程管理

---

## 12. 后续优化方向

1. 添加用户登录和权限管理
2. 审查历史和对比功能
3. 规则管理界面
4. WebSocket实时进度
5. 数据统计分析
6. Docker容器化部署
