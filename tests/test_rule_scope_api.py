import json

from web.app import create_app
from web.models import Database


def _app_with_temp_overrides(tmp_path, monkeypatch, overrides):
    overrides_path = tmp_path / "rule_overrides.json"
    overrides_path.write_text(json.dumps(overrides, ensure_ascii=False), encoding="utf-8")

    import config.rule_overrides as rule_overrides

    monkeypatch.setattr(rule_overrides, "OVERRIDES_FILE", str(overrides_path))

    app = create_app()
    app.config["TESTING"] = True
    app.db = Database(str(tmp_path / "database.db"))
    return app, overrides_path


def test_existing_custom_rule_scope_can_be_updated_and_read_back(tmp_path, monkeypatch):
    app, overrides_path = _app_with_temp_overrides(tmp_path, monkeypatch, {
        "rule_p_003": {
            "source": "product_rules",
            "name": "寿命要求",
            "description": "审查寿命要求是否完整",
            "category": "custom",
            "severity": "error",
            "review_type": "llm",
            "enabled": True,
            "code": "P-003",
            "logic": "若文档中寿命要求包括贮存期、首翻期、总寿命的信息内容，则通过；否则，不通过",
            "standard_ref": "",
            "params": {},
            "scope": "all",
        }
    })

    response = app.test_client().put(
        "/rules/api/rules/rule_p_003",
        json={
            "enabled": True,
            "severity": "error",
            "code": "P-003",
            "logic": "若文档中寿命要求包括贮存期、首翻期、总寿命的信息内容，则通过；否则，不通过",
            "standard_ref": "",
            "scope": "body",
            "name": "寿命要求",
            "description": "审查寿命要求是否完整",
        },
    )

    assert response.status_code == 200
    assert app.test_client().get("/rules/api/rules/rule_p_003").get_json()["scope"] == "body"
    saved = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert saved["rule_p_003"]["scope"] == "body"


def test_builtin_rule_scope_can_be_updated_and_read_back(tmp_path, monkeypatch):
    app, overrides_path = _app_with_temp_overrides(tmp_path, monkeypatch, {})

    response = app.test_client().put(
        "/rules/api/rules/format",
        json={
            "enabled": True,
            "severity": "warning",
            "review_type": "rule",
            "code": "FM-001",
            "logic": "检查格式",
            "standard_ref": "",
            "scope": "cover",
        },
    )

    assert response.status_code == 200
    assert app.test_client().get("/rules/api/rules/format").get_json()["scope"] == "cover"
    saved = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert saved["format"]["scope"] == "cover"


def test_created_rule_scope_is_saved_and_read_back(tmp_path, monkeypatch):
    app, overrides_path = _app_with_temp_overrides(tmp_path, monkeypatch, {})

    response = app.test_client().post(
        "/rules/api/rules",
        json={
            "source": "product_rules",
            "name": "新规则",
            "description": "新规则描述",
            "severity": "warning",
            "code": "N-001",
            "logic": "检查正文内容",
            "standard_ref": "",
            "scope": "body",
            "params": {},
        },
    )

    assert response.status_code == 200
    rule_id = response.get_json()["rule_id"]
    assert app.test_client().get(f"/rules/api/rules/{rule_id}").get_json()["scope"] == "body"
    saved = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert saved[rule_id]["scope"] == "body"


def test_created_table_field_rule_type_and_params_are_saved_and_read_back(tmp_path, monkeypatch):
    app, overrides_path = _app_with_temp_overrides(tmp_path, monkeypatch, {})

    response = app.test_client().post(
        "/rules/api/rules",
        json={
            "source": "product_rules",
            "name": "编号格式",
            "description": "检查封面编号格式",
            "severity": "error",
            "review_type": "rule",
            "code": "P-007",
            "logic": "封面表格中的编号应以 JB- 开头",
            "standard_ref": "",
            "scope": "cover",
            "params": {
                "check_type": "table_field_regex",
                "field_labels": ["文件编号", "编号"],
                "match_mode": "starts_with",
                "match_value": "JB-",
            },
        },
    )

    assert response.status_code == 200
    rule_id = response.get_json()["rule_id"]
    loaded = app.test_client().get(f"/rules/api/rules/{rule_id}").get_json()
    assert loaded["review_type"] == "rule"
    assert loaded["scope"] == "cover"
    assert loaded["params"]["check_type"] == "table_field_regex"
    assert loaded["params"]["field_labels"] == ["文件编号", "编号"]
    assert loaded["params"]["match_mode"] == "starts_with"
    assert loaded["params"]["match_value"] == "JB-"
    assert loaded["params"]["pattern"] == "^JB-.+"

    saved = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert saved[rule_id]["review_type"] == "rule"
    assert saved[rule_id]["params"]["match_mode"] == "starts_with"
    assert saved[rule_id]["params"]["match_value"] == "JB-"
    assert saved[rule_id]["params"]["pattern"] == "^JB-.+"


def test_updating_custom_rule_review_type_is_saved_and_read_back(tmp_path, monkeypatch):
    app, overrides_path = _app_with_temp_overrides(tmp_path, monkeypatch, {
        "rule_p_006": {
            "source": "product_rules",
            "name": "阶段标识",
            "description": "检查阶段标识是否正确",
            "category": "custom",
            "severity": "error",
            "review_type": "llm",
            "enabled": True,
            "code": "P-006",
            "logic": "阶段标识应以 -AB 结尾",
            "standard_ref": "",
            "params": {},
            "scope": "cover",
        }
    })

    response = app.test_client().put(
        "/rules/api/rules/rule_p_006",
        json={
            "enabled": True,
            "severity": "error",
            "review_type": "rule",
            "code": "P-006",
            "logic": "阶段标识应以 -AB 结尾",
            "standard_ref": "",
            "scope": "cover",
            "name": "阶段标识",
            "description": "检查阶段标识是否正确",
            "params": {
                "check_type": "table_field_regex",
                "field_labels": ["阶段标识", "审查阶段标识"],
                "match_mode": "ends_with",
                "match_value": "-AB",
            },
        },
    )

    assert response.status_code == 200
    loaded = app.test_client().get("/rules/api/rules/rule_p_006").get_json()
    assert loaded["review_type"] == "rule"
    assert loaded["params"]["match_mode"]["value"] == "ends_with"
    assert loaded["params"]["match_value"]["value"] == "-AB"
    assert loaded["params"]["pattern"]["value"] == "^.+-AB$"

    saved = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert saved["rule_p_006"]["review_type"] == "rule"
    assert saved["rule_p_006"]["params"]["match_mode"]["value"] == "ends_with"
    assert saved["rule_p_006"]["params"]["match_value"]["value"] == "-AB"
    assert saved["rule_p_006"]["params"]["pattern"]["value"] == "^.+-AB$"
