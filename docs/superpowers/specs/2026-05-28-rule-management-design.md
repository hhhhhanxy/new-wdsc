# 规则管理功能设计

## 背景

当前系统没有规则查看/管理页面。"航空作动系统"规则集在审查页仅显示为一个标签，用户无法看到规则集内的具体规则，也无法调整规则属性。

## 目标

新增规则管理页面，支持按规则集分组浏览规则，并提供完整管理能力：启用/禁用、严重级别、审查属性、规则参数的动态编辑。

## 页面结构

路由：`/rules/`，侧边栏新增"规则管理"导航项。

采用双栏布局（与审查页一致）：

- **左侧栏**：规则集列表，显示每个规则集名称和规则数量，底部显示统计信息（总规则数、启用/禁用数）。点击切换右侧内容。
- **右侧栏**：选中规则集的规则表格，每行显示规则 ID、名称、阶段、审查类型、严重级别、启用状态，末尾有编辑和禁用操作按钮。

规则集按 `rule.source` 字段分组：
- `source="common"` → 通用规则
- `source="aviation"` → 航空作动系统
- `source="extension"` → 扩展规则

## 编辑弹窗

点击"编辑"弹出 Modal，包含以下区域：

1. **基本信息**（只读）：规则 ID、名称、描述
2. **基本属性**（可编辑）：启用状态（开关）、严重级别（下拉）、审查类型（RULE/LLM/BOTH）、审查阶段（下拉）
3. **规则参数**（可编辑）：动态渲染，按规则各不同。没有 params 的规则不显示此区域
4. **适用文档类型**（可编辑）：多选复选框

规则参数通过 `rule.params` 字段定义，格式：

```python
params = {
    "keywords": {
        "label": "必须包含术语",
        "type": "tag_list",   # tag_list / number / text / select
        "value": ["作动筒", "伺服阀"],
    },
    "threshold": {
        "label": "匹配阈值",
        "type": "number",
        "value": 3,
        "min": 1,
        "max": 10,
    }
}
```

前端根据 `type` 字段渲染对应控件：`tag_list`（标签输入）、`number`（数字框）、`text`（文本框）、`select`（下拉）。

## API 设计

| 路由 | 方法 | 用途 |
|------|------|------|
| `/rules/` | GET | 渲染规则管理页面 |
| `/rules/api/profiles` | GET | 返回所有规则集及规则列表 |
| `/rules/api/rules/<rule_id>` | GET | 返回单条规则详情（含参数） |
| `/rules/api/rules/<rule_id>` | PUT | 更新规则属性 |

## 数据持久化

规则修改保存在 `config/rule_overrides.json`，只存储被修改过的字段：

```json
{
  "actuator_keywords": {
    "enabled": false,
    "severity": "error",
    "review_type": "both",
    "phase": "completeness",
    "params": { "keywords": { "value": ["作动筒", "伺服阀"] } }
  }
}
```

启动时将 override merge 到默认值上。未修改的字段不写入文件。新增规则自动忽略。残留 override（对应规则已删除）在 merge 时按 rule_id 匹配，找不到则跳过。

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| override 文件不存在 | 首次保存时自动创建 |
| override 中有非法值 | 忽略该字段，用默认值，日志 warn |
| 前端传了规则不存在的字段 | 忽略多余字段 |
| 前端传了非法枚举值 | 返回 400 + 错误信息 |
| 并发编辑同一条规则 | 后写覆盖（单用户场景） |

## 审查页联动

审查页"规则集"标签旁新增"查看规则"链接，跳转到 `/rules/` 并定位到对应规则集。

## 涉及文件

- `web/routes/rules.py`（新增）：规则管理路由和 API
- `web/templates/rules.html`（新增）：规则管理页面模板
- `web/routes/__init__.py`：注册新路由
- `web/templates/base.html`：侧边栏新增导航项
- `web/templates/review.html`：规则集标签旁添加链接
- `rules/base_rule.py`：Rule dataclass 新增 `params` 字段
- `rules/loaders/rule_loader.py`：加载时应用 rule_overrides.json
- `config/rule_overrides.json`（新增）：规则覆盖持久化文件
- `web/static/css/style.css`：弹窗等新增样式
