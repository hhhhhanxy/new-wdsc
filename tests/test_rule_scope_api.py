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
