# 规则管理功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增规则管理页面，支持按规则集分组浏览、编辑规则属性（启用/禁用、严重级别、审查类型、阶段、参数），持久化到 JSON 文件。

**Architecture:** 后端新增 Flask blueprint 提供页面和 REST API，规则修改持久化到 `config/rule_overrides.json`，启动时 merge 到默认值。前端双栏布局+弹窗编辑，复用现有 CSS 变量和组件风格。

**Tech Stack:** Flask (Blueprint), Jinja2, vanilla JS, JSON file persistence

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `rules/base_rule.py` | Rule dataclass 新增 `params` 字段 |
| Create | `config/rule_overrides.py` | override JSON 文件读写 + merge 逻辑 |
| Modify | `rules/loaders/rule_loader.py` | 加载后应用 overrides |
| Create | `web/routes/rules.py` | 规则管理页面 + API 路由 |
| Modify | `web/app.py` | 注册 rules blueprint |
| Modify | `web/templates/base.html` | 侧边栏新增导航项 |
| Create | `web/templates/rules.html` | 规则管理页面模板 |
| Modify | `web/static/css/style.css` | 新增弹窗、标签输入、开关样式 |
| Modify | `web/templates/review.html` | 规则集标签旁加"查看规则"链接 |

---

### Task 1: Rule dataclass 新增 params 字段

**Files:**
- Modify: `rules/base_rule.py:89-100`

- [ ] **Step 1: 在 Rule dataclass 新增 params 字段**

在 `rules/base_rule.py` 的 `Rule` 类中，在 `doc_types` 字段后新增：

```python
@dataclass
class Rule:
    rule_id: str
    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    enabled: bool = True
    check_func: Optional[Callable] = None
    source: str = "common"
    review_type: ReviewType = ReviewType.RULE
    phase: ReviewPhase = ReviewPhase.FORMAT
    doc_types: List[DocumentType] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
```

注意需要在文件顶部导入中确认 `Dict` 和 `Any` 已包含在 typing 导入中：
```python
from typing import List, Optional, Callable, Any, Dict
```

- [ ] **Step 2: 验证现有代码不受影响**

Run: `cd d:/code/new-wdsc && python -c "from rules.base_rule import Rule; r = Rule(rule_id='t', name='t', description='t', category=None, severity=None); print('params:', r.params)"`

Expected: `params: {}`

- [ ] **Step 3: Commit**

```bash
git add rules/base_rule.py
git commit -m "feat: add params field to Rule dataclass for dynamic rule parameters"
```

---

### Task 2: 为现有规则添加 params 示例数据

**Files:**
- Modify: `rules/aviation/actuator_rules.py:21-34`
- Modify: `rules/common/format.py:79-90`
- Modify: `rules/common/grammar.py:58-69`

- [ ] **Step 1: 为 actuator_keywords 规则添加 params**

修改 `rules/aviation/actuator_rules.py` 中的 `create_actuator_rules` 函数：

```python
def create_actuator_rules():
    return [
        Rule(
            rule_id="actuator_keywords",
            name="作动系统关键术语检查",
            description="检查文档是否包含作动系统关键术语",
            category=RuleCategory.CONTENT,
            severity=RuleSeverity.WARNING,
            check_func=check_actuator_keywords,
            source="aviation",
            enabled=False,
            review_type=ReviewType.LLM,
            params={
                "keywords": {
                    "label": "必须包含术语",
                    "type": "tag_list",
                    "value": ["作动器", "冗余", "液压", "电传"],
                }
            }
        )
    ]
```

- [ ] **Step 2: 为 format 规则添加 params**

修改 `rules/common/format.py` 中的 `create_format_rule` 函数，在 Rule 构造中添加 `params`：

```python
def create_format_rule() -> Rule:
    checker = FormatChecker()

    return Rule(
        rule_id="format",
        name="格式检查",
        description="检查标点、空格和排版问题",
        category=RuleCategory.FORMAT,
        severity=RuleSeverity.WARNING,
        check_func=checker.check,
        review_type=ReviewType.BOTH,
        params={
            "check_punctuation": {
                "label": "检查标点符号",
                "type": "select",
                "value": "yes",
                "options": ["yes", "no"],
            },
            "max_consecutive_spaces": {
                "label": "最大连续空格数",
                "type": "number",
                "value": 3,
                "min": 1,
                "max": 10,
            }
        }
    )
```

- [ ] **Step 3: 为 grammar 规则添加 params**

修改 `rules/common/grammar.py` 中的 `create_grammar_rule` 函数，在 Rule 构造中添加 `params`：

```python
def create_grammar_rule() -> Rule:
    checker = GrammarChecker()

    return Rule(
        rule_id="grammar",
        name="语法检查",
        description="检查常见语法错误（如的地得）",
        category=RuleCategory.CONTENT,
        severity=RuleSeverity.WARNING,
        check_func=checker.check,
        review_type=ReviewType.BOTH,
        params={
            "check_de_di_de": {
                "label": "检查的地得用法",
                "type": "select",
                "value": "yes",
                "options": ["yes", "no"],
            }
        }
    )
```

- [ ] **Step 4: 验证规则加载正常**

Run: `cd d:/code/new-wdsc && python -c "from rules.loaders.rule_loader import RuleLoader; rules = RuleLoader.load_all_rules('aviation', include_extensions=False); [print(r.rule_id, r.params) for r in rules]"`

Expected: 3 条规则各自打印出 params 字典内容。

- [ ] **Step 5: Commit**

```bash
git add rules/aviation/actuator_rules.py rules/common/format.py rules/common/grammar.py
git commit -m "feat: add params metadata to existing rules"
```

---

### Task 3: 创建 rule_overrides 持久化模块

**Files:**
- Create: `config/rule_overrides.py`

- [ ] **Step 1: 创建 config/rule_overrides.py**

```python
"""规则覆盖持久化模块。

将运行时对规则属性的修改保存到 config/rule_overrides.json，
启动时加载并 merge 到默认规则上。
"""
import json
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

OVERRIDES_FILE = os.path.join(os.path.dirname(__file__), "rule_overrides.json")

VALID_OVERRIDE_FIELDS = {"enabled", "severity", "review_type", "phase", "params"}


def load_overrides() -> Dict[str, Dict[str, Any]]:
    """从 JSON 文件加载规则覆盖配置。"""
    if not os.path.exists(OVERRIDES_FILE):
        return {}
    try:
        with open(OVERRIDES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("rule_overrides.json 格式错误，忽略")
            return {}
        return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("加载 rule_overrides.json 失败: %s", e)
        return {}


def save_overrides(overrides: Dict[str, Dict[str, Any]]):
    """保存规则覆盖配置到 JSON 文件。"""
    os.makedirs(os.path.dirname(OVERRIDES_FILE), exist_ok=True)
    with open(OVERRIDES_FILE, "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2)
    logger.info("规则覆盖已保存到 %s", OVERRIDES_FILE)


def apply_overrides(rules: List) -> List:
    """将 override 配置 merge 到规则列表上。"""
    overrides = load_overrides()

    if not overrides:
        return rules

    for rule in rules:
        rule_overrides = overrides.get(rule.rule_id)
        if not rule_overrides:
            continue

        for field_name, value in rule_overrides.items():
            if field_name not in VALID_OVERRIDE_FIELDS:
                logger.debug("忽略未知字段 %s.%s", rule.rule_id, field_name)
                continue

            if field_name == "severity":
                from rules.base_rule import RuleSeverity
                try:
                    value = RuleSeverity(value)
                except ValueError:
                    logger.warning("非法 severity 值 %s for %s，跳过", value, rule.rule_id)
                    continue
            elif field_name == "review_type":
                from rules.base_rule import ReviewType
                try:
                    value = ReviewType(value)
                except ValueError:
                    logger.warning("非法 review_type 值 %s for %s，跳过", value, rule.rule_id)
                    continue
            elif field_name == "phase":
                from rules.base_rule import ReviewPhase
                try:
                    value = ReviewPhase(value)
                except ValueError:
                    logger.warning("非法 phase 值 %s for %s，跳过", value, rule.rule_id)
                    continue

            try:
                setattr(rule, field_name, value)
            except AttributeError:
                logger.warning("无法设置字段 %s.%s", rule.rule_id, field_name)

    return rules


def update_rule_override(rule_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """更新单条规则的 override 并保存。只存储被修改的字段。"""
    # 过滤掉非法字段
    filtered = {k: v for k, v in updates.items() if k in VALID_OVERRIDE_FIELDS}
    if not filtered:
        return {"error": "没有有效的更新字段"}

    # 序列化枚举值
    for key in ("severity", "review_type", "phase"):
        if key in filtered and hasattr(filtered[key], "value"):
            filtered[key] = filtered[key].value

    # 序列化 params 中的枚举值
    if "params" in filtered and isinstance(filtered["params"], dict):
        serialized_params = {}
        for pk, pv in filtered["params"].items():
            if isinstance(pv, dict) and "value" in pv:
                serialized_params[pk] = pv
            else:
                serialized_params[pk] = {"value": pv}
        filtered["params"] = serialized_params

    overrides = load_overrides()
    if rule_id not in overrides:
        overrides[rule_id] = {}
    overrides[rule_id].update(filtered)
    save_overrides(overrides)

    return {"ok": True, "rule_id": rule_id, "updated_fields": list(filtered.keys())}
```

- [ ] **Step 2: 验证模块可导入**

Run: `cd d:/code/new-wdsc && python -c "from config.rule_overrides import load_overrides, save_overrides, apply_overrides, update_rule_override; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add config/rule_overrides.py
git commit -m "feat: add rule_overrides persistence module"
```

---

### Task 4: RuleLoader 集成 overrides

**Files:**
- Modify: `rules/loaders/rule_loader.py:34-52`

- [ ] **Step 1: 在 load_all_rules 末尾应用 overrides**

修改 `rules/loaders/rule_loader.py` 的 `load_all_rules` 方法：

```python
@staticmethod
def load_all_rules(profile: str = "default", include_extensions: bool = True) -> List[Rule]:
    rules: List[Rule] = []

    # 1. 通用规则
    rules.extend(RuleLoader.load_common_rules())

    # 2. 行业规则
    profile_map = {
        "aviation": RuleLoader.load_aviation_rules,
    }

    if profile in profile_map:
        rules.extend(profile_map[profile]())

    # 3. 扩展规则
    if include_extensions:
        rules.extend(RuleLoader.load_extension_rules())

    # 4. 应用用户覆盖
    from config.rule_overrides import apply_overrides
    rules = apply_overrides(rules)

    return rules
```

- [ ] **Step 2: 验证 override 流程**

Run: `cd d:/code/new-wdsc && python -c "from config.rule_overrides import save_overrides; save_overrides({'format': {'enabled': False}}); from rules.loaders.rule_loader import RuleLoader; rules = RuleLoader.load_all_rules('aviation', include_extensions=False); f=[r for r in rules if r.rule_id=='format'][0]; print('format enabled:', f.enabled)"`

Expected: `format enabled: False`

- [ ] **Step 3: 清理测试数据并 Commit**

Run: `rm -f d:/code/new-wdsc/config/rule_overrides.json`

```bash
git add rules/loaders/rule_loader.py
git commit -m "feat: apply rule_overrides during rule loading"
```

---

### Task 5: 创建规则管理 API 路由

**Files:**
- Create: `web/routes/rules.py`

- [ ] **Step 1: 创建 web/routes/rules.py**

```python
"""规则管理页面和 API 路由。"""
from flask import Blueprint, render_template, request, jsonify, current_app

from rules.base_rule import (
    Rule, RuleSeverity, ReviewType, ReviewPhase, PHASE_ORDER,
    PHASE_DISPLAY_NAMES, RuleCategory,
)
from rules.loaders.rule_loader import RuleLoader
from config.rule_overrides import update_rule_override

bp = Blueprint("rules", __name__)

# 规则集显示名称映射
SOURCE_DISPLAY = {
    "common": "通用规则",
    "aviation": "航空作动系统",
    "extension": "扩展规则",
}

# 规则集排序顺序
SOURCE_ORDER = {"common": 0, "aviation": 1, "extension": 2}


def _serialize_rule(rule: Rule) -> dict:
    """将 Rule 对象序列化为 JSON 安全的字典。"""
    return {
        "rule_id": rule.rule_id,
        "name": rule.name,
        "description": rule.description,
        "category": rule.category.value,
        "severity": rule.severity.value,
        "enabled": rule.enabled,
        "source": rule.source,
        "review_type": rule.review_type.value,
        "phase": rule.phase.value,
        "phase_display": PHASE_DISPLAY_NAMES.get(rule.phase, rule.phase.value),
        "doc_types": [dt.value for dt in rule.doc_types],
        "params": rule.params,
    }


def _group_rules_by_source(rules: list) -> list:
    """按 source 分组规则，返回有序列表。"""
    groups = {}
    for rule in rules:
        src = rule.source
        if src not in groups:
            groups[src] = {
                "source": src,
                "display_name": SOURCE_DISPLAY.get(src, src),
                "rules": [],
            }
        groups[src]["rules"].append(_serialize_rule(rule))

    result = sorted(groups.values(), key=lambda g: SOURCE_ORDER.get(g["source"], 99))

    # 统计
    total = len(rules)
    enabled = sum(1 for r in rules if r.enabled)
    for g in result:
        g["total"] = len(g["rules"])
        g["enabled"] = sum(1 for r in g["rules"] if r["enabled"])

    return result, total, enabled


@bp.route("/")
def index():
    """渲染规则管理页面。"""
    rules = RuleLoader.load_all_rules("aviation", include_extensions=False)
    groups, total, enabled = _group_rules_by_source(rules)
    return render_template(
        "rules.html",
        active_page="rules",
        groups=groups,
        total=total,
        enabled_count=enabled,
        disabled_count=total - enabled,
        phases=[{"value": p.value, "label": PHASE_DISPLAY_NAMES[p]} for p in PHASE_ORDER],
        severities=[{"value": s.value, "label": {"error": "错误", "warning": "警告", "info": "信息"}.get(s.value, s.value)} for s in RuleSeverity],
        review_types=[{"value": t.value, "label": {"rule": "规则引擎", "llm": "LLM", "both": "规则+LLM"}.get(t.value, t.value)} for t in ReviewType],
    )


@bp.route("/api/profiles")
def api_profiles():
    """返回所有规则集及规则列表。"""
    rules = RuleLoader.load_all_rules("aviation", include_extensions=False)
    groups, total, enabled = _group_rules_by_source(rules)
    return jsonify({"groups": groups, "total": total, "enabled": enabled})


@bp.route("/api/rules/<rule_id>")
def api_get_rule(rule_id: str):
    """返回单条规则详情。"""
    rules = RuleLoader.load_all_rules("aviation", include_extensions=False)
    rule = next((r for r in rules if r.rule_id == rule_id), None)
    if not rule:
        return jsonify({"error": f"规则 {rule_id} 不存在"}), 404
    return jsonify(_serialize_rule(rule))


@bp.route("/api/rules/<rule_id>", methods=["PUT"])
def api_update_rule(rule_id: str):
    """更新规则属性。"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    # 验证枚举值
    if "severity" in data:
        try:
            RuleSeverity(data["severity"])
        except ValueError:
            return jsonify({"error": f"非法的 severity 值: {data['severity']}"}), 400

    if "review_type" in data:
        try:
            ReviewType(data["review_type"])
        except ValueError:
            return jsonify({"error": f"非法的 review_type 值: {data['review_type']}"}), 400

    if "phase" in data:
        try:
            ReviewPhase(data["phase"])
        except ValueError:
            return jsonify({"error": f"非法的 phase 值: {data['phase']}"}), 400

    result = update_rule_override(rule_id, data)
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)
```

- [ ] **Step 2: 验证模块可导入**

Run: `cd d:/code/new-wdsc && python -c "from web.routes.rules import bp; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add web/routes/rules.py
git commit -m "feat: add rules management API routes"
```

---

### Task 6: 注册 blueprint 到 Flask app

**Files:**
- Modify: `web/app.py:29-35`

- [ ] **Step 1: 在 app.py 中注册 rules blueprint**

在 `web/app.py` 的 blueprint 注册区域添加 rules 导入和注册：

```python
    # Register blueprints
    from web.routes import bp as index_bp
    from web.routes.review import bp as review_bp
    from web.routes.generate import bp as generate_bp
    from web.routes.rules import bp as rules_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(review_bp, url_prefix='/review')
    app.register_blueprint(generate_bp, url_prefix='/generate')
    app.register_blueprint(rules_bp, url_prefix='/rules')
```

- [ ] **Step 2: 验证 app 启动**

Run: `cd d:/code/new-wdsc && python -c "from web.app import create_app; app = create_app(); print([r.rule for r in app.url_map.iter_rules() if '/rules' in r.rule])"`

Expected: 输出包含 `/rules/`, `/rules/api/profiles`, `/rules/api/rules/<rule_id>` 的列表。

- [ ] **Step 3: Commit**

```bash
git add web/app.py
git commit -m "feat: register rules blueprint in Flask app"
```

---

### Task 7: 侧边栏新增导航项

**Files:**
- Modify: `web/templates/base.html:24-34`

- [ ] **Step 1: 在侧边栏 nav 中添加规则管理链接**

在 `web/templates/base.html` 的 `<nav class="sidebar-nav">` 中，在"文档生成"链接后添加：

```html
        <nav class="sidebar-nav">
            <a href="/" class="{{ 'active' if active_page == 'index' else '' }}" onclick="closeSidebarMobile()">
                <span class="nav-icon">&#9776;</span> <span>首页</span>
            </a>
            <a href="/review/" class="{{ 'active' if active_page == 'review' else '' }}" onclick="closeSidebarMobile()">
                <span class="nav-icon">&#128269;</span> <span>文档审查</span>
            </a>
            <a href="/generate/" class="{{ 'active' if active_page == 'generate' else '' }}" onclick="closeSidebarMobile()">
                <span class="nav-icon">&#9997;</span> <span>文档生成</span>
            </a>
            <a href="/rules/" class="{{ 'active' if active_page == 'rules' else '' }}" onclick="closeSidebarMobile()">
                <span class="nav-icon">&#128295;</span> <span>规则管理</span>
            </a>
        </nav>
```

- [ ] **Step 2: Commit**

```bash
git add web/templates/base.html
git commit -m "feat: add rules management nav item to sidebar"
```

---

### Task 8: 审查页添加"查看规则"链接

**Files:**
- Modify: `web/templates/review.html:34-38`

- [ ] **Step 1: 在规则集标签旁添加链接**

将 `web/templates/review.html` 中的规则集 config-row 替换为：

```html
            <div class="config-row">
                <div class="config-label">规则集</div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span class="badge badge-info">航空作动系统</span>
                    <a href="/rules/" style="font-size:11px;color:var(--primary);text-decoration:none;">查看规则 &rarr;</a>
                </div>
            </div>
```

- [ ] **Step 2: Commit**

```bash
git add web/templates/review.html
git commit -m "feat: add 'view rules' link on review page"
```

---

### Task 9: 新增 CSS 样式

**Files:**
- Modify: `web/static/css/style.css`

- [ ] **Step 1: 在 CSS 文件末尾（responsive 媒体查询之前）添加规则管理页面样式**

在 `web/static/css/style.css` 的 `/* ========== Responsive ========== */` 注释行之前插入：

```css
/* ========== Rule Management ========== */

/* Rule set list in left column */
.rule-set-list {
    list-style: none;
}

.rule-set-item {
    padding: 12px 16px;
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: background 0.15s;
    margin-bottom: 4px;
}

.rule-set-item:hover {
    background: var(--bg);
}

.rule-set-item.active {
    background: #e3f2fd;
    border-left: 3px solid var(--primary);
}

.rule-set-item .set-name {
    font-size: 13px;
    font-weight: 500;
}

.rule-set-item .set-count {
    font-size: 11px;
    color: var(--text-secondary);
    background: var(--bg);
    padding: 2px 8px;
    border-radius: 10px;
}

/* Rule stats bar */
.rule-stats {
    display: flex;
    gap: 16px;
    padding: 12px 0;
    margin-top: 12px;
    border-top: 1px solid var(--border);
    font-size: 12px;
    color: var(--text-secondary);
}

/* Rule table */
.rule-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}

.rule-table th {
    text-align: left;
    padding: 8px 10px;
    background: var(--bg);
    font-weight: 600;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
}

.rule-table td {
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
}

.rule-table tr:last-child td {
    border-bottom: none;
}

.rule-table tr:hover td {
    background: #fafafa;
}

.rule-name-cell {
    font-weight: 500;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.rule-id-cell {
    font-family: monospace;
    font-size: 11px;
    color: var(--text-secondary);
}

/* Status dot */
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.status-dot.on {
    background: var(--success);
}

.status-dot.off {
    background: #bdbdbd;
}

/* Action buttons in table */
.rule-actions {
    display: flex;
    gap: 6px;
}

.rule-actions .btn {
    padding: 4px 10px;
    font-size: 11px;
}

/* Modal overlay */
.modal-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 200;
    justify-content: center;
    align-items: center;
}

.modal-overlay.open {
    display: flex;
}

.modal {
    background: var(--card);
    border-radius: 10px;
    width: 560px;
    max-width: 90vw;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
}

.modal-header h3 {
    font-size: 15px;
    font-weight: 600;
}

.modal-close {
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    color: var(--text-secondary);
    padding: 4px;
}

.modal-body {
    padding: 20px;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 20px;
    border-top: 1px solid var(--border);
}

/* Modal form fields */
.modal-field {
    margin-bottom: 14px;
}

.modal-field label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 4px;
}

.modal-field .readonly {
    font-size: 13px;
    color: var(--text);
    padding: 4px 0;
}

.modal-field select,
.modal-field input[type="number"],
.modal-field input[type="text"] {
    width: 100%;
    padding: 7px 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 13px;
    outline: none;
}

.modal-field select:focus,
.modal-field input:focus {
    border-color: var(--primary);
}

/* Toggle switch */
.toggle-switch {
    position: relative;
    display: inline-block;
    width: 40px;
    height: 22px;
}

.toggle-switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background: #bdbdbd;
    border-radius: 22px;
    transition: background 0.2s;
}

.toggle-slider::before {
    content: "";
    position: absolute;
    width: 18px;
    height: 18px;
    left: 2px;
    bottom: 2px;
    background: #fff;
    border-radius: 50%;
    transition: transform 0.2s;
}

.toggle-switch input:checked + .toggle-slider {
    background: var(--success);
}

.toggle-switch input:checked + .toggle-slider::before {
    transform: translateX(18px);
}

/* Tag list input */
.tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 6px;
    border: 1px solid var(--border);
    border-radius: 6px;
    min-height: 36px;
    align-items: center;
}

.tag-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: #e3f2fd;
    color: var(--primary);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
}

.tag-item .tag-remove {
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
    color: var(--primary);
    opacity: 0.6;
}

.tag-item .tag-remove:hover {
    opacity: 1;
}

.tag-input {
    border: none;
    outline: none;
    font-size: 12px;
    flex: 1;
    min-width: 60px;
    padding: 2px;
}

/* Section divider in modal */
.modal-divider {
    font-size: 11px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 14px;
    margin-top: 20px;
}

/* Doc type checkboxes */
.doc-type-checks {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
}

.doc-type-checks label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    font-weight: normal;
    cursor: pointer;
}

/* Review type radio buttons */
.review-type-btns {
    display: flex;
    gap: 8px;
}

.review-type-btns label {
    padding: 4px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
}

.review-type-btns input:checked + span {
    color: var(--primary);
}

.review-type-btns label:has(input:checked) {
    border-color: var(--primary);
    background: #e3f2fd;
}

.review-type-btns input {
    display: none;
}
```

- [ ] **Step 2: Commit**

```bash
git add web/static/css/style.css
git commit -m "feat: add CSS styles for rules management page and edit modal"
```

---

### Task 10: 创建规则管理页面模板

**Files:**
- Create: `web/templates/rules.html`

- [ ] **Step 1: 创建 web/templates/rules.html**

```html
{% extends "base.html" %}
{% block title %}规则管理 - 文档审查与生成平台{% endblock %}

{% block content %}
<div class="page-header">
    <h1>规则管理</h1>
    <p>查看和管理审查规则集，编辑规则属性和参数</p>
</div>

<div class="two-col">
    <!-- Left: Rule set list -->
    <div>
        <div class="panel">
            <div class="panel-title">规则集</div>
            <ul class="rule-set-list" id="ruleSetList">
                <!-- JS rendered -->
            </ul>
            <div class="rule-stats" id="ruleStats"></div>
        </div>
    </div>

    <!-- Right: Rules table -->
    <div>
        <div class="panel">
            <div class="panel-title" id="currentSetTitle">请选择规则集</div>
            <table class="rule-table" id="ruleTable" style="display:none;">
                <thead>
                    <tr>
                        <th>状态</th>
                        <th>规则名称</th>
                        <th>阶段</th>
                        <th>类型</th>
                        <th>级别</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="ruleTableBody"></tbody>
            </table>
            <div class="empty-state" id="noRulesHint">选择左侧规则集查看规则列表</div>
        </div>
    </div>
</div>

<!-- Edit Modal -->
<div class="modal-overlay" id="editModal">
    <div class="modal">
        <div class="modal-header">
            <h3 id="modalTitle">编辑规则</h3>
            <button class="modal-close" onclick="closeModal()">&times;</button>
        </div>
        <div class="modal-body" id="modalBody">
            <!-- JS rendered -->
        </div>
        <div class="modal-footer">
            <button class="btn btn-outline" onclick="closeModal()">取消</button>
            <button class="btn btn-primary" onclick="saveRule()">保存</button>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
// Data from server
const groups = {{ groups | tojson }};
const totalCount = {{ total }};
const enabledCount = {{ enabled_count }};
const disabledCount = {{ disabled_count }};
const phases = {{ phases | tojson }};
const severities = {{ severities | tojson }};
const reviewTypes = {{ review_types | tojson }};

let currentGroup = null;
let currentRule = null;

// Severity display helpers
const severityLabels = {};
severities.forEach(s => severityLabels[s.value] = s.label);

const severityBadges = {
    error: 'badge-danger',
    warning: 'badge-warning',
    info: 'badge-info',
};

const reviewTypeLabels = {};
reviewTypes.forEach(t => reviewTypeLabels[t.value] = t.label);

const phaseLabels = {};
phases.forEach(p => phaseLabels[p.value] = p.label);

// Render rule set list
function renderSetList() {
    const list = document.getElementById('ruleSetList');
    list.innerHTML = groups.map(g => `
        <li class="rule-set-item" data-source="${g.source}" onclick="selectGroup('${g.source}')">
            <span class="set-name">${g.display_name}</span>
            <span class="set-count">${g.enabled}/${g.total}</span>
        </li>
    `).join('');

    document.getElementById('ruleStats').innerHTML =
        `共 ${totalCount} 条规则 &middot; 已启用 ${enabledCount} &middot; 已禁用 ${disabledCount}`;
}

function selectGroup(source) {
    currentGroup = groups.find(g => g.source === source);
    if (!currentGroup) return;

    document.querySelectorAll('.rule-set-item').forEach(el => el.classList.remove('active'));
    document.querySelector(`[data-source="${source}"]`).classList.add('active');

    document.getElementById('currentSetTitle').textContent = currentGroup.display_name;
    document.getElementById('noRulesHint').style.display = 'none';
    document.getElementById('ruleTable').style.display = '';

    renderRuleTable(currentGroup.rules);
}

function renderRuleTable(rules) {
    const tbody = document.getElementById('ruleTableBody');
    tbody.innerHTML = rules.map(r => `
        <tr>
            <td><span class="status-dot ${r.enabled ? 'on' : 'off'}" title="${r.enabled ? '已启用' : '已禁用'}"></span></td>
            <td>
                <div class="rule-name-cell" title="${r.name}">${r.name}</div>
                <div class="rule-id-cell">${r.rule_id}</div>
            </td>
            <td>${phaseLabels[r.phase] || r.phase}</td>
            <td>${reviewTypeLabels[r.review_type] || r.review_type}</td>
            <td><span class="badge ${severityBadges[r.severity] || 'badge-default'}">${severityLabels[r.severity] || r.severity}</span></td>
            <td>
                <div class="rule-actions">
                    <button class="btn btn-outline" onclick="openEdit('${r.rule_id}')">编辑</button>
                    <button class="btn btn-outline" onclick="toggleEnabled('${r.rule_id}', ${!r.enabled})">${r.enabled ? '禁用' : '启用'}</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// Toggle enabled
function toggleEnabled(ruleId, newState) {
    fetch('/rules/api/rules/' + ruleId, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({enabled: newState}),
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) { alert(data.error); return; }
        // Update local data and re-render
        for (const g of groups) {
            const rule = g.rules.find(r => r.rule_id === ruleId);
            if (rule) {
                rule.enabled = newState;
                g.enabled = g.rules.filter(r => r.enabled).length;
                break;
            }
        }
        selectGroup(currentGroup.source);
        renderSetList();
        // Re-select current group
        document.querySelector(`[data-source="${currentGroup.source}"]`).classList.add('active');
    });
}

// Edit modal
function openEdit(ruleId) {
    fetch('/rules/api/rules/' + ruleId)
        .then(r => r.json())
        .then(rule => {
            currentRule = rule;
            document.getElementById('modalTitle').textContent = '编辑规则 - ' + rule.name;
            renderModalBody(rule);
            document.getElementById('editModal').classList.add('open');
        });
}

function closeModal() {
    document.getElementById('editModal').classList.remove('open');
    currentRule = null;
}

function renderModalBody(rule) {
    let html = '';

    // Read-only info
    html += `<div class="modal-field"><label>规则ID</label><div class="readonly">${rule.rule_id}</div></div>`;
    html += `<div class="modal-field"><label>描述</label><div class="readonly">${rule.description}</div></div>`;

    // Divider
    html += `<div class="modal-divider">基本属性</div>`;

    // Enabled toggle
    html += `<div class="modal-field"><label>启用状态</label>
        <label class="toggle-switch">
            <input type="checkbox" id="editEnabled" ${rule.enabled ? 'checked' : ''}>
            <span class="toggle-slider"></span>
        </label>
    </div>`;

    // Severity
    html += `<div class="modal-field"><label>严重级别</label>
        <select id="editSeverity">
            ${severities.map(s => `<option value="${s.value}" ${rule.severity === s.value ? 'selected' : ''}>${s.label}</option>`).join('')}
        </select>
    </div>`;

    // Review type
    html += `<div class="modal-field"><label>审查类型</label>
        <div class="review-type-btns">
            ${reviewTypes.map(t => `
                <label><input type="radio" name="editReviewType" value="${t.value}" ${rule.review_type === t.value ? 'checked' : ''}><span>${t.label}</span></label>
            `).join('')}
        </div>
    </div>`;

    // Phase
    html += `<div class="modal-field"><label>审查阶段</label>
        <select id="editPhase">
            ${phases.map(p => `<option value="${p.value}" ${rule.phase === p.value ? 'selected' : ''}>${p.label}</option>`).join('')}
        </select>
    </div>`;

    // Params
    if (rule.params && Object.keys(rule.params).length > 0) {
        html += `<div class="modal-divider">规则参数</div>`;
        for (const [key, param] of Object.entries(rule.params)) {
            html += renderParamField(key, param);
        }
    }

    document.getElementById('modalBody').innerHTML = html;
}

function renderParamField(key, param) {
    const label = param.label || key;
    const type = param.type || 'text';

    if (type === 'tag_list') {
        const values = param.value || [];
        return `<div class="modal-field">
            <label>${label}</label>
            <div class="tag-list" id="param_${key}">
                ${values.map(v => `<span class="tag-item">${v}<span class="tag-remove" onclick="this.parentElement.remove()">&times;</span></span>`).join('')}
                <input class="tag-input" placeholder="输入后回车添加" onkeydown="addTag(event, '${key}')">
            </div>
        </div>`;
    }

    if (type === 'number') {
        const min = param.min !== undefined ? `min="${param.min}"` : '';
        const max = param.max !== undefined ? `max="${param.max}"` : '';
        return `<div class="modal-field">
            <label>${label}</label>
            <input type="number" id="param_${key}" value="${param.value !== undefined ? param.value : ''}" ${min} ${max}>
        </div>`;
    }

    if (type === 'select') {
        const options = param.options || [];
        return `<div class="modal-field">
            <label>${label}</label>
            <select id="param_${key}">
                ${options.map(o => `<option value="${o}" ${param.value === o ? 'selected' : ''}>${o}</option>`).join('')}
            </select>
        </div>`;
    }

    // text
    return `<div class="modal-field">
        <label>${label}</label>
        <input type="text" id="param_${key}" value="${param.value !== undefined ? param.value : ''}">
    </div>`;
}

function addTag(event, key) {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    const input = event.target;
    const value = input.value.trim();
    if (!value) return;

    const tagHtml = `<span class="tag-item">${value}<span class="tag-remove" onclick="this.parentElement.remove()">&times;</span></span>`;
    input.insertAdjacentHTML('beforebegin', tagHtml);
    input.value = '';
}

function saveRule() {
    if (!currentRule) return;

    const updates = {
        enabled: document.getElementById('editEnabled').checked,
        severity: document.getElementById('editSeverity').value,
        review_type: document.querySelector('input[name="editReviewType"]:checked').value,
        phase: document.getElementById('editPhase').value,
    };

    // Collect params
    if (currentRule.params && Object.keys(currentRule.params).length > 0) {
        const params = {};
        for (const [key, param] of Object.entries(currentRule.params)) {
            const type = param.type || 'text';
            if (type === 'tag_list') {
                const container = document.getElementById('param_' + key);
                const tags = container.querySelectorAll('.tag-item');
                params[key] = {label: param.label, type: param.type, value: Array.from(tags).map(t => t.textContent.replace('×', '').trim())};
            } else if (type === 'number') {
                const val = parseFloat(document.getElementById('param_' + key).value);
                params[key] = {label: param.label, type: param.type, value: val};
            } else {
                const el = document.getElementById('param_' + key);
                params[key] = {label: param.label, type: param.type, value: el.value};
            }
        }
        updates.params = params;
    }

    fetch('/rules/api/rules/' + currentRule.rule_id, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(updates),
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) { alert(data.error); return; }
        // Reload profiles to get fresh data
        fetch('/rules/api/profiles')
            .then(r => r.json())
            .then(profileData => {
                // Update local data
                groups.length = 0;
                groups.push(...profileData.groups);
                closeModal();
                renderSetList();
                if (currentGroup) selectGroup(currentGroup.source);
            });
    });
}

// Close modal on overlay click
document.getElementById('editModal').addEventListener('click', function(e) {
    if (e.target === this) closeModal();
});

// Initial render
renderSetList();
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add web/templates/rules.html
git commit -m "feat: add rules management page template with edit modal"
```

---

### Task 11: 端到端验证

- [ ] **Step 1: 启动 Flask 应用**

Run: `cd d:/code/new-wdsc && python -m web.app` (后台运行)

- [ ] **Step 2: 验证页面可访问**

Run: `curl -s http://localhost:5000/rules/ | head -20`

Expected: HTML 页面包含 "规则管理" 标题

- [ ] **Step 3: 验证 API 端点**

Run: `curl -s http://localhost:5000/rules/api/profiles | python -m json.tool`

Expected: JSON 包含 groups 数组，每个 group 有 source, display_name, rules 列表

- [ ] **Step 4: 验证规则更新**

Run:
```bash
curl -s -X PUT http://localhost:5000/rules/api/rules/format \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}' | python -m json.tool
```

Expected: `{"ok": true, "rule_id": "format", "updated_fields": ["enabled"]}`

- [ ] **Step 5: 验证 override 文件已生成**

Run: `cat d:/code/new-wdsc/config/rule_overrides.json`

Expected: JSON 文件包含 format 规则的 override

- [ ] **Step 6: 验证 override 生效**

Run: `curl -s http://localhost:5000/rules/api/profiles | python -m json.tool | grep -A2 '"rule_id": "format"'`

Expected: `"enabled": false`

- [ ] **Step 7: 清理测试数据**

Run: `rm -f d:/code/new-wdsc/config/rule_overrides.json`

- [ ] **Step 8: 最终提交（如有修复）**

```bash
git add -A
git commit -m "fix: address e2e validation issues"
```
