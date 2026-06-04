from web.app import create_app
from web.models import Database
from web.time_utils import beijing_now_str


def _test_app(tmp_path):
    app = create_app()
    app.config["TESTING"] = True
    app.db = Database(str(tmp_path / "database.db"))
    return app


def test_delete_finished_review_task_record(tmp_path):
    app = _test_app(tmp_path)
    task_id = app.db.create_review_task("done.docx", "done.docx", "by_rule")
    app.db.update_review_task(task_id, status="completed", progress=100)

    response = app.test_client().delete(f"/review/delete/{task_id}")

    assert response.status_code == 200
    assert response.get_json()["deleted"] == 1
    assert app.db.get_review_task(task_id) is None


def test_delete_running_review_task_record_stops_and_deletes(tmp_path):
    app = _test_app(tmp_path)
    task_id = app.db.create_review_task("running.docx", "running.docx", "by_rule")
    app.db.update_review_task(task_id, status="processing", progress=50)
    app.db.conn.execute(
        "UPDATE review_tasks SET created_at = ? WHERE id = ?",
        (beijing_now_str(), task_id),
    )
    app.db.conn.commit()

    response = app.test_client().delete(f"/review/delete/{task_id}")

    assert response.status_code == 200
    assert response.get_json()["stopped"] is True
    assert app.db.get_review_task(task_id) is None


def test_delete_stale_running_review_task_record_is_allowed(tmp_path):
    app = _test_app(tmp_path)
    task_id = app.db.create_review_task("stale.docx", "stale.docx", "by_rule")
    app.db.update_review_task(task_id, status="processing", progress=50)
    app.db.conn.execute(
        "UPDATE review_tasks SET created_at = ? WHERE id = ?",
        ("2026-05-28 08:11:04", task_id),
    )
    app.db.conn.commit()

    response = app.test_client().delete(f"/review/delete/{task_id}")

    assert response.status_code == 200
    assert app.db.get_review_task(task_id) is None


def test_delete_all_review_records_keeps_running_tasks(tmp_path):
    app = _test_app(tmp_path)
    completed_id = app.db.create_review_task("done.docx", "done.docx", "by_rule")
    failed_id = app.db.create_review_task("failed.docx", "failed.docx", "by_rule")
    running_id = app.db.create_review_task("running.docx", "running.docx", "by_rule")
    app.db.update_review_task(completed_id, status="completed", progress=100)
    app.db.update_review_task(failed_id, status="failed", progress=100)
    app.db.update_review_task(running_id, status="processing", progress=50)
    app.db.conn.execute(
        "UPDATE review_tasks SET created_at = ? WHERE id = ?",
        (beijing_now_str(), running_id),
    )
    app.db.conn.commit()

    response = app.test_client().delete("/review/delete-all")

    assert response.status_code == 200
    assert response.get_json()["deleted"] == 2
    assert app.db.get_review_task(completed_id) is None
    assert app.db.get_review_task(failed_id) is None
    assert app.db.get_review_task(running_id)["status"] == "processing"


def test_delete_stale_review_records_only_removes_stale_running_tasks(tmp_path):
    app = _test_app(tmp_path)
    stale_id = app.db.create_review_task("stale.docx", "stale.docx", "by_rule")
    running_id = app.db.create_review_task("running.docx", "running.docx", "by_rule")
    app.db.update_review_task(stale_id, status="processing", progress=50)
    app.db.update_review_task(running_id, status="processing", progress=50)
    app.db.conn.execute(
        "UPDATE review_tasks SET created_at = ? WHERE id = ?",
        ("2026-05-28 08:11:04", stale_id),
    )
    app.db.conn.execute(
        "UPDATE review_tasks SET created_at = ? WHERE id = ?",
        (beijing_now_str(), running_id),
    )
    app.db.conn.commit()

    response = app.test_client().delete("/review/delete-stale")

    assert response.status_code == 200
    assert response.get_json()["deleted"] == 1
    assert app.db.get_review_task(stale_id) is None
    assert app.db.get_review_task(running_id)["status"] == "processing"


def test_cancel_running_review_task(tmp_path):
    app = _test_app(tmp_path)
    task_id = app.db.create_review_task("running.docx", "running.docx", "by_rule")
    app.db.update_review_task(task_id, status="processing", progress=50)

    response = app.test_client().post(f"/review/cancel/{task_id}")

    assert response.status_code == 200
    task = app.db.get_review_task(task_id)
    assert task["status"] == "canceled"
    assert task["error"] == "用户手动停止审查"
    assert task["completed_at"]


def test_cancel_finished_review_task_is_rejected(tmp_path):
    app = _test_app(tmp_path)
    task_id = app.db.create_review_task("done.docx", "done.docx", "by_rule")
    app.db.update_review_task(task_id, status="completed", progress=100)

    response = app.test_client().post(f"/review/cancel/{task_id}")

    assert response.status_code == 400
    assert app.db.get_review_task(task_id)["status"] == "completed"
