import json
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from web.app import create_app
from web.models import Database


HEADERS = [
    "序号",
    "规则编号 *",
    "规则名称 *",
    "检查要求 *",
    "规则说明",
    "审查方式 *",
    "问题级别 *",
    "检查范围 *",
    "目标章节",
    "必须包含的内容",
    "依据文件/条款",
    "检查类型\n仅规则引擎",
    "字段名称\n仅规则引擎",
    "匹配方式\n仅规则引擎",
    "匹配内容\n仅规则引擎",
    "填写状态",
]


def _column_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _xlsx_bytes(data_rows):
    all_rows = [HEADERS, *data_rows]
    row_xml = []
    for row_number, values in enumerate(all_rows, 1):
        cells = []
        for column, value in enumerate(values, 1):
            reference = f"{_column_name(column)}{row_number}"
            cells.append(
                f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value or ""))}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    worksheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData></worksheet>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="规则导入" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return output.getvalue()


def _test_app(tmp_path, monkeypatch, existing_overrides=None):
    overrides_path = tmp_path / "rule_overrides.json"
    overrides_path.write_text(
        json.dumps(existing_overrides or {}, ensure_ascii=False),
        encoding="utf-8",
    )
    custom_sets_path = tmp_path / "custom_rule_sets.json"
    custom_sets_path.write_text(
        json.dumps({"test_outline": {"display_name": "试验大纲规则"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    import config.rule_overrides as rule_overrides
    import web.routes.rules as rules_routes

    monkeypatch.setattr(rule_overrides, "OVERRIDES_FILE", str(overrides_path))
    monkeypatch.setattr(rules_routes, "CUSTOM_SETS_FILE", str(custom_sets_path))
    monkeypatch.setattr(rules_routes, "RULE_IMPORT_BATCHES_FILE", tmp_path / "rule_import_batches.json")

    app = create_app()
    app.config["TESTING"] = True
    app.db = Database(str(tmp_path / "database.db"))
    return app, overrides_path


def _upload(client, file_bytes, commit=False, source="test_outline", duplicate_mode="reject", partial=False):
    return client.post(
        f"/rules/api/sets/{source}/import",
        data={
            "commit": "true" if commit else "false",
            "duplicate_mode": duplicate_mode,
            "partial": "true" if partial else "false",
            "file": (BytesIO(file_bytes), "rules.xlsx"),
        },
        content_type="multipart/form-data",
    )


def test_rule_import_preview_and_commit_defaults_to_enabled(tmp_path, monkeypatch):
    app, overrides_path = _test_app(tmp_path, monkeypatch)
    workbook = _xlsx_bytes([[
        1,
        "T-001",
        "试验项目范围完整性检查",
        "范围章节必须包含温度、高度、温度变化和湿热，缺少任一项时不通过",
        "检查自然环境类鉴定试验覆盖情况",
        "LLM",
        "错误",
        "正文",
        "范围；试验项目",
        "温度；高度；温度变化；湿热",
        "项目试验要求第 3.1 条",
        "",
        "",
        "",
        "",
        "",
    ]])

    preview = _upload(app.test_client(), workbook).get_json()
    assert preview["ok"] is True
    assert preview["valid_count"] == 1

    response = _upload(app.test_client(), workbook, commit=True)
    assert response.status_code == 200
    assert response.get_json()["imported_count"] == 1

    saved = json.loads(overrides_path.read_text(encoding="utf-8"))
    imported = next(iter(saved.values()))
    assert imported["source"] == "test_outline"
    assert imported["code"] == "T-001"
    assert imported["enabled"] is True
    assert imported["target_headings"] == ["范围", "试验项目"]


def test_rule_import_reports_duplicate_code_without_partial_write(tmp_path, monkeypatch):
    app, overrides_path = _test_app(tmp_path, monkeypatch, {
        "rule_t_001": {
            "source": "test_outline",
            "name": "已有规则",
            "description": "",
            "category": "custom",
            "severity": "warning",
            "review_type": "llm",
            "enabled": True,
            "code": "T-001",
            "logic": "已有检查逻辑",
            "standard_ref": "",
            "params": {},
            "scope": "body",
        }
    })
    workbook = _xlsx_bytes([[
        1, "T-001", "重复规则", "检查内容", "", "LLM", "警告", "正文",
        "", "", "", "", "", "", "", "",
    ]])

    response = _upload(app.test_client(), workbook, commit=True)
    assert response.status_code == 400
    assert response.get_json()["error_count"] == 1
    row = response.get_json()["rows"][0]
    assert any("规则编号" in error and "已存在" in error for error in row["errors"])
    assert row["error_details"][0]["cell"] == "B2"
    saved = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert list(saved) == ["rule_t_001"]


def test_rule_engine_import_requires_engine_columns(tmp_path, monkeypatch):
    app, _ = _test_app(tmp_path, monkeypatch)
    workbook = _xlsx_bytes([[
        1, "T-002", "阶段标识格式", "阶段标识应以 -AB 结尾", "", "规则引擎", "警告", "封面",
        "", "", "", "", "", "", "", "",
    ]])

    response = _upload(app.test_client(), workbook)
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is False
    assert data["error_count"] == 1
    assert any("字段名称" in error and "需要填写" in error for error in data["rows"][0]["errors"])
    assert any(detail["cell"] == "M2" for detail in data["rows"][0]["error_details"])


def test_rule_import_requires_existing_rule_set(tmp_path, monkeypatch):
    app, _ = _test_app(tmp_path, monkeypatch)
    workbook = _xlsx_bytes([])
    response = _upload(app.test_client(), workbook, source="missing_set")
    assert response.status_code == 404
    assert "请先创建规则集" in response.get_json()["error"]


def test_duplicate_rule_can_be_skipped_or_updated_and_batch_rolled_back(tmp_path, monkeypatch):
    original = {
        "source": "test_outline",
        "name": "原规则",
        "description": "",
        "category": "custom",
        "severity": "warning",
        "review_type": "llm",
        "enabled": True,
        "code": "T-010",
        "logic": "原检查要求必须满足，否则不通过",
        "standard_ref": "",
        "params": {},
        "scope": "body",
        "target_headings": [],
        "required_elements": [],
        "aliases": ["T-010", "原规则"],
    }
    app, overrides_path = _test_app(tmp_path, monkeypatch, {"rule_t_010": original})
    workbook = _xlsx_bytes([[
        1, "T-010", "更新后规则", "新检查要求必须满足，否则不通过", "", "LLM", "错误", "正文",
        "", "", "", "", "", "", "", "",
    ]])

    skipped = _upload(app.test_client(), workbook, duplicate_mode="skip").get_json()
    assert skipped["skip_count"] == 1
    assert skipped["valid_count"] == 0

    updated = _upload(app.test_client(), workbook, commit=True, duplicate_mode="update")
    assert updated.status_code == 200
    data = updated.get_json()
    assert data["updated_count"] == 1
    saved = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert saved["rule_t_010"]["name"] == "更新后规则"

    rollback = app.test_client().post(f"/rules/api/import-batches/{data['batch_id']}/rollback")
    assert rollback.status_code == 200
    restored = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert restored["rule_t_010"] == original


def test_partial_import_only_writes_valid_rows(tmp_path, monkeypatch):
    app, overrides_path = _test_app(tmp_path, monkeypatch)
    workbook = _xlsx_bytes([
        [1, "T-020", "有效规则", "正文必须包含范围，否则不通过", "", "LLM", "警告", "正文", "", "", "", "", "", "", "", ""],
        [2, "T-021", "", "", "", "LLM", "警告", "正文", "", "", "", "", "", "", "", ""],
    ])

    blocked = _upload(app.test_client(), workbook, commit=True)
    assert blocked.status_code == 400
    partial = _upload(app.test_client(), workbook, commit=True, partial=True)
    assert partial.status_code == 200
    assert partial.get_json()["created_count"] == 1
    saved = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert [item["code"] for item in saved.values()] == ["T-020"]


def test_import_issue_workbook_can_be_downloaded(tmp_path, monkeypatch):
    app, _ = _test_app(tmp_path, monkeypatch)
    workbook = _xlsx_bytes([[
        1, "T-030", "内容检查", "检查是否合理", "", "LLM", "警告", "正文",
        "", "", "", "", "", "", "", "",
    ]])
    response = app.test_client().post(
        "/rules/api/sets/test_outline/import-issues",
        data={
            "duplicate_mode": "reject",
            "file": (BytesIO(workbook), "rules.xlsx"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert response.data.startswith(b"PK")
