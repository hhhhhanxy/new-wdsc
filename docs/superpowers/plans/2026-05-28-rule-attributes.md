# 规则属性改进 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Rule 新增编号（code）、判定逻辑（logic）、标准依据（standard_ref）三个业务字段，更新规则管理页面展示和编辑，补充现有规则数据。

**Architecture:** 在 Rule dataclass 上新增三个字符串字段，后端序列化和 override 持久化同步扩展，前端表格新增编号列并移除阶段列，弹窗新增基本信息区域并移除审查阶段字段。

**Tech Stack:** Python dataclass, Flask/Jinja2, vanilla JS

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `rules/base_rule.py` | Rule dataclass 新增 code, logic, standard_ref |
| Modify | `config/rule_overrides.py` | VALID_OVERRIDE_FIELDS 新增三个字段 |
| Modify | `rules/common/format.py` | 补充 code, logic, standard_ref 数据 |
| Modify | `rules/common/grammar.py` | 同上 |
| Modify | `rules/aviation/actuator_rules.py` | 同上 |
| Modify | `web/routes/rules.py` | _serialize_rule 返回新字段 |
| Modify | `web/templates/rules.html` | 表格新增编号列移除阶段列，弹窗新增基本信息移除阶段 |

---

### Task 1: Rule dataclass 新增字段

**Files:**
- Modify: `rules/base_rule.py:100-101`

- [ ] **Step 1: 在 Rule dataclass 的 params 字段后新增三个字段**

当前 Rule dataclass 末尾两行是：
```python
    doc_types: List[DocumentType] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
```

在 `params` 行之后添加：
```python
    code: str = ""
    logic: str = ""
    standard_ref: str = ""
```

- [ ] **Step 2: 验证字段存在**

Run: `cd d:/code/new-wdsc && python -c "from rules.base_rule import Rule; r = Rule(rule_id='t', name='t', description='t', category=None, severity=None); print(f'code={r.code!r} logic={r.logic!r} standard_ref={r.standard_ref!r}')"`
Expected: `code='' logic='' standard_ref=''`

- [ ] **Step 3: Commit**

```bash
git add rules/base_rule.py
git commit -m "feat: add code, logic, standard_ref fields to Rule dataclass

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: override 持久化模块新增字段

**Files:**
- Modify: `config/rule_overrides.py`

- [ ] **Step 1: 在 VALID_OVERRIDE_FIELDS 集合中新增三个字段**

当前代码：
```python
VALID_OVERRIDE_FIELDS = {"enabled", "severity", "review_type", "phase", "params"}
CUSTOM_RULE_FIELDS = {"source", "name", "description", "category"}
```

改为：
```python
VALID_OVERRIDE_FIELDS = {"enabled", "severity", "review_type", "phase", "params", "code", "logic", "standard_ref"}
CUSTOM_RULE_FIELDS = {"source", "name", "description", "category"}
```

- [ ] **Step 2: 验证**

Run: `cd d:/code/new-wdsc && python -c "from config.rule_overrides import VALID_OVERRIDE_FIELDS; assert 'code' in VALID_OVERRIDE_FIELDS; assert 'logic' in VALID_OVERRIDE_FIELDS; assert 'standard_ref' in VALID_OVERRIDE_FIELDS; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add config/rule_overrides.py
git commit -m "feat: add code, logic, standard_ref to override fields

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 为现有三条规则补充业务数据

**Files:**
- Modify: `rules/common/format.py:79-105`
- Modify: `rules/common/grammar.py:58-77`
- Modify: `rules/aviation/actuator_rules.py:21-42`

- [ ] **Step 1: format.py — 补充 code, logic, standard_ref**

在 `create_format_rule()` 的 Rule 构造函数中，在 `params={...}` 后新增：

```python
        code="FM-001",
        logic="逐字符扫描文本，检测连续标点符号、标点前空格、中英文标点混排、连续多余空格、行尾空格、标题行首空格等格式问题，匹配到任一模式即判定不通过",
        standard_ref="GJB 438B 第6.1节 文档格式要求",
```

- [ ] **Step 2: grammar.py — 补充 code, logic, standard_ref**

在 `create_grammar_rule()` 的 Rule 构造函数中，在 `params={...}` 后新增：

```python
        code="GR-001",
        logic="逐词扫描"的、地、得"用法，依据语法规则判断其后应接名词、动词或形容词/副词，使用不当即判定不通过",
        standard_ref="GB/T 15834 标点符号用法",
```

- [ ] **Step 3: actuator_rules.py — 补充 code, logic, standard_ref**

在 `create_actuator_rules()` 的 Rule 构造函数中，在 `params={...}` 后新增：

```python
            code="AV-001",
            logic="检查文档是否包含作动器、冗余、液压、电传四个关键术语，缺少任一即判定不通过",
            standard_ref="GJB 438B 第5.3.2条 关键术语要求",
```

- [ ] **Step 4: 验证规则加载**

Run: `cd d:/code/new-wdsc && python -c "from rules.loaders.rule_loader import RuleLoader; rules = RuleLoader.load_all_rules('aviation', include_extensions=False); [print(f'{r.rule_id:20s} code={r.code:6s} logic={r.logic[:30]}...') for r in rules]"`
Expected: 3 rules with non-empty code and logic fields.

- [ ] **Step 5: Commit**

```bash
git add rules/common/format.py rules/common/grammar.py rules/aviation/actuator_rules.py
git commit -m "feat: add code, logic, standard_ref data to existing rules

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 后端序列化和页面数据传递

**Files:**
- Modify: `web/routes/rules.py`

- [ ] **Step 1: _serialize_rule 新增三个字段**

在 `_serialize_rule` 函数中，在 `"params": rule.params,` 行之后添加：

```python
        "code": rule.code,
        "logic": rule.logic,
        "standard_ref": rule.standard_ref,
```

- [ ] **Step 2: 验证 API 返回新字段**

Run: `cd d:/code/new-wdsc && python -c "from web.app import create_app; app = create_app(); client = app.test_client(); resp = client.get('/rules/api/rules/actuator_keywords'); r = resp.get_json(); print(f'code={r[\"code\"]} logic={r[\"logic\"][:30]}... standard_ref={r[\"standard_ref\"]}')"`
Expected: `code=AV-001 logic=检查文档是否包含作动器、冗余、液压、电传四个... standard_ref=GJB 438B 第5.3.2条 关键术语要求`

- [ ] **Step 3: Commit**

```bash
git add web/routes/rules.py
git commit -m "feat: serialize code, logic, standard_ref in rule API

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 前端 — 表格新增编号列，移除阶段列

**Files:**
- Modify: `web/templates/rules.html`

- [ ] **Step 1: 修改表格 thead — 移除"阶段"列，新增"编号"列**

找到规则表格 `<thead>` 中的 `<tr>` 行，当前是：
```html
<th>状态</th>
<th>规则名称</th>
<th>阶段</th>
<th>类型</th>
<th>级别</th>
<th>操作</th>
```

替换为：
```html
<th>编号</th>
<th>规则描述</th>
<th>级别</th>
<th>操作</th>
```

- [ ] **Step 2: 修改 renderRuleTable 的 tbody 渲染**

找到 `renderRuleTable` 函数中的 `tbody.innerHTML` 模板，将整个 `<tr>...</tr>` 替换为：

```javascript
        <tr>
            <td><span class="rule-id-cell">${r.code || r.rule_id}</span></td>
            <td>
                <div class="rule-name-cell" title="${r.name}">${r.name}</div>
            </td>
            <td><span class="badge ${severityBadges[r.severity] || 'badge-default'}">${severityLabels[r.severity] || r.severity}</span></td>
            <td>
                <div class="rule-actions">
                    <button class="btn btn-outline" onclick="openEdit('${r.rule_id}')">编辑</button>
                    <button class="btn btn-outline" onclick="toggleEnabled('${r.rule_id}', ${!r.enabled})">${r.enabled ? '禁用' : '启用'}</button>
                    ${r.custom ? `<button class="btn btn-outline" style="color:var(--danger);" onclick="deleteRule('${r.rule_id}')">删除</button>` : ''}
                </div>
            </td>
        </tr>
```

- [ ] **Step 3: 验证页面渲染**

Run: `cd d:/code/new-wdsc && python -c "from web.app import create_app; app = create_app(); client = app.test_client(); resp = client.get('/rules/'); html = resp.data.decode(); assert '编号' in html; assert '阶段' not in html.split('操作')[0].split('编号')[-1]; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add web/templates/rules.html
git commit -m "feat: add code column, remove phase column from rules table

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 前端 — 编辑弹窗新增基本信息区域，移除审查阶段

**Files:**
- Modify: `web/templates/rules.html`

- [ ] **Step 1: 修改 renderModalBody 函数 — 新增基本信息区域，移除阶段选择**

找到 `renderModalBody` 函数体，将函数内从 `let html = '';` 到 `document.getElementById('modalBody').innerHTML = html;` 的整个内容替换为：

```javascript
    let html = '';

    // ── 基本信息 ──
    html += `<div class="modal-divider">基本信息</div>`;
    html += `<div class="modal-field"><label>编号</label>
        <input type="text" id="editCode" value="${rule.code || ''}" placeholder="如 AV-001">
    </div>`;
    html += `<div class="modal-field"><label>规则描述</label>
        <input type="text" id="editName" value="${rule.name}">
    </div>`;
    html += `<div class="modal-field"><label>详细说明</label>
        <input type="text" id="editDesc" value="${rule.description}">
    </div>`;
    html += `<div class="modal-field"><label>判定逻辑</label>
        <textarea id="editLogic" rows="3" style="width:100%;padding:7px 10px;border:1px solid var(--border);border-radius:6px;font-size:13px;outline:none;resize:vertical;">${rule.logic || ''}</textarea>
    </div>`;
    html += `<div class="modal-field"><label>标准依据</label>
        <input type="text" id="editStandardRef" value="${rule.standard_ref || ''}" placeholder="如 GJB 438B 第5.3.2条">
    </div>`;

    // ── 审查属性 ──
    html += `<div class="modal-divider">审查属性</div>`;
    html += `<div class="modal-field"><label>启用状态</label>
        <label class="toggle-switch">
            <input type="checkbox" id="editEnabled" ${rule.enabled ? 'checked' : ''}>
            <span class="toggle-slider"></span>
        </label>
    </div>`;
    html += `<div class="modal-field"><label>严重级别</label>
        <select id="editSeverity">
            ${severities.map(s => `<option value="${s.value}" ${rule.severity === s.value ? 'selected' : ''}>${s.label}</option>`).join('')}
        </select>
    </div>`;

    // ── 规则参数 ──
    if (rule.params && Object.keys(rule.params).length > 0) {
        html += `<div class="modal-divider">规则参数</div>`;
        for (const [key, param] of Object.entries(rule.params)) {
            html += renderParamField(key, param);
        }
    }

    document.getElementById('modalBody').innerHTML = html;
```

- [ ] **Step 2: 修改 saveRule 函数 — 新增字段收集**

找到 `saveRule` 函数中构建 `updates` 对象的部分，替换为：

```javascript
    const updates = {
        enabled: document.getElementById('editEnabled').checked,
        severity: document.getElementById('editSeverity').value,
        name: document.getElementById('editName').value,
        description: document.getElementById('editDesc').value,
        code: document.getElementById('editCode').value,
        logic: document.getElementById('editLogic').value,
        standard_ref: document.getElementById('editStandardRef').value,
    };
```

注意：`review_type` 和 `phase` 不再从弹窗收集，它们保留内部值不变。

- [ ] **Step 3: 验证页面加载和弹窗渲染**

Run: `cd d:/code/new-wdsc && python -c "from web.app import create_app; app = create_app(); client = app.test_client(); resp = client.get('/rules/'); assert resp.status_code == 200; print('Page OK')"`
Expected: `Page OK`

- [ ] **Step 4: Commit**

```bash
git add web/templates/rules.html
git commit -m "feat: add code/logic/standard_ref to edit modal, remove phase

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: 端到端验证

- [ ] **Step 1: 验证规则列表包含新字段**

Run: `cd d:/code/new-wdsc && python -c "
from rules.loaders.rule_loader import RuleLoader
rules = RuleLoader.load_all_rules('aviation', include_extensions=False)
for r in rules:
    assert r.code, f'{r.rule_id} missing code'
    assert r.logic, f'{r.rule_id} missing logic'
    assert r.standard_ref, f'{r.rule_id} missing standard_ref'
    print(f'{r.code:6s} {r.rule_id:20s} OK')
print('All rules have new fields')
"`

- [ ] **Step 2: 验证 API 返回新字段**

Run: `cd d:/code/new-wdsc && python -c "
from web.app import create_app
app = create_app()
client = app.test_client()
resp = client.get('/rules/api/profiles')
data = resp.get_json()
for g in data['groups']:
    for r in g['rules']:
        assert 'code' in r
        assert 'logic' in r
        assert 'standard_ref' in r
        print(f'{r[\"code\"]:6s} {r[\"name\"]}')
print('API OK')
"`

- [ ] **Step 3: 验证 override 保存新字段**

Run: `cd d:/code/new-wdsc && python -c "
from web.app import create_app
app = create_app()
client = app.test_client()
# 更新 code
resp = client.put('/rules/api/rules/format', json={'code': 'FM-001-TEST'})
assert resp.get_json()['ok']
# 验证生效
resp = client.get('/rules/api/rules/format')
assert resp.get_json()['code'] == 'FM-001-TEST'
print('Override OK')
# 清理
import os; os.remove('config/rule_overrides.json') if os.path.exists('config/rule_overrides.json') else None
"`

- [ ] **Step 4: Commit（如有修复）**

```bash
git add -A
git commit -m "fix: address e2e validation issues

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
