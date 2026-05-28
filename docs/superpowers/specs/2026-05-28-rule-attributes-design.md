# 规则属性改进设计

## 背景

当前规则缺少面向用户的业务属性（编号、判定逻辑、标准依据），规则管理页面展示的信息不够完整，不利于审查人员理解规则的依据和判定标准。

## 目标

为每条规则新增三个面向用户的业务字段：编号（code）、判定逻辑（logic）、标准依据（standard_ref），并在规则管理页面完整展示和编辑。

## Rule dataclass 新增字段

```python
# 新增字段（加在 params 之后）
code: str = ""              # 业务编号，如 "AV-001"
logic: str = ""             # 判定逻辑文字描述
standard_ref: str = ""      # 标准依据（自由文字，后期可关联标准库）
```

- `rule_id` 保持不变，是系统内部引用键（序列化、override、API 路由都用它）
- `code` 是给用户看的业务编号
- 三个新字段默认空字符串，不影响现有规则

## API 改动

- `_serialize_rule` 返回新增的 `code`、`logic`、`standard_ref`
- `VALID_OVERRIDE_FIELDS`（`config/rule_overrides.py`）加入 `code`、`logic`、`standard_ref`

## 规则管理页面 UI 改动

### 规则表格

新增"编号"列，移除"阶段"列：

| 编号 | 规则描述 | 级别 | 操作 |
|------|---------|------|------|
| AV-001 | 作动系统关键术语检查 | ... | ... |

### 编辑弹窗

在编辑弹窗中新增"基本信息"区域，移除"审查阶段"字段：

- 编号（text input）
- 规则描述（text input）
- 详细说明（text input，对应 description）
- 判定逻辑（textarea，多行文本）
- 标准依据（text input）

"审查属性"区域简化为：启用状态、严重级别。"审查阶段"从弹窗中移除，phase 字段保留在 dataclass 上作为内部属性，不在 UI 展示。"规则参数"区域保持不变。

## 现有规则补充数据

| 规则 | code | logic | standard_ref |
|------|------|-------|-------------|
| format | FM-001 | 逐字符扫描文本，检测连续标点符号、标点前空格、中英文标点混排、连续多余空格、行尾空格、标题行首空格等格式问题，匹配到任一模式即判定不通过 | GJB 438B 第6.1节 文档格式要求 |
| grammar | GR-001 | 逐词扫描"的、地、得"用法，依据语法规则判断其后应接名词、动词或形容词/副词，使用不当即判定不通过 | GB/T 15834 标点符号用法 |
| actuator_keywords | AV-001 | 检查文档是否包含作动器、冗余、液压、电传四个关键术语，缺少任一即判定不通过 | GJB 438B 第5.3.2条 关键术语要求 |

## 涉及文件

- `rules/base_rule.py` — Rule dataclass 新增 3 个字段
- `config/rule_overrides.py` — VALID_OVERRIDE_FIELDS 新增 3 个字段
- `rules/common/format.py` — 补充 code、logic、standard_ref
- `rules/common/grammar.py` — 同上
- `rules/aviation/actuator_rules.py` — 同上
- `web/routes/rules.py` — `_serialize_rule` 返回新字段
- `web/templates/rules.html` — 表格新增编号列，弹窗新增基本信息区域
