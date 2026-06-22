from web.app import create_app
from web.models import Database


def _test_app(tmp_path):
    app = create_app()
    app.config["TESTING"] = True
    app.db = Database(str(tmp_path / "database.db"))
    return app


def test_delete_all_generate_records_keeps_running_tasks(tmp_path):
    app = _test_app(tmp_path)
    completed_id = app.db.create_generate_task(
        "requirement",
        "需求文档模板",
        {"title": "已完成文档"},
    )
    failed_id = app.db.create_generate_task(
        "requirement",
        "需求文档模板",
        {"title": "失败文档"},
    )
    running_id = app.db.create_generate_task(
        "requirement",
        "需求文档模板",
        {"title": "生成中文档"},
    )
    app.db.update_generate_task(completed_id, status="completed", progress=100)
    app.db.update_generate_task(failed_id, status="failed", progress=100)
    app.db.update_generate_task(running_id, status="processing", progress=50)

    response = app.test_client().delete("/generate/delete-all")

    assert response.status_code == 200
    assert response.get_json()["deleted"] == 2
    assert response.get_json()["remaining"] == 1
    assert app.db.get_generate_task(completed_id) is None
    assert app.db.get_generate_task(failed_id) is None
    assert app.db.get_generate_task(running_id)["status"] == "processing"


def test_delete_all_generate_records_removes_canceled_tasks(tmp_path):
    app = _test_app(tmp_path)
    canceled_id = app.db.create_generate_task(
        "requirement",
        "需求文档模板",
        {"title": "已停止文档"},
    )
    app.db.update_generate_task(canceled_id, status="canceled", progress=30)

    response = app.test_client().delete("/generate/delete-all")

    assert response.status_code == 200
    assert response.get_json()["deleted"] == 1
    assert response.get_json()["remaining"] == 0
    assert app.db.get_generate_task(canceled_id) is None
