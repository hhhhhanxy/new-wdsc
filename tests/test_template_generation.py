import json

from docx import Document


class FakeLLMResponse:
    def __init__(self, content):
        self.content = content


class FakeLLMClient:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, system_prompt=None):
        self.prompts.append(prompt)
        return FakeLLMResponse("本章节内容基于用户输入生成。")


def test_template_manager_serializes_templates():
    from templates.template_manager import TemplateManager

    templates = TemplateManager().list_template_dicts()

    assert templates
    assert any(t["id"] == "technical_specification" for t in templates)
    assert all("chapters" in t for t in templates)


def test_template_manager_persists_custom_templates(tmp_path):
    from templates.template_manager import TemplateManager

    store_path = tmp_path / "generation_templates.json"
    manager = TemplateManager(custom_store_path=str(store_path))
    template = manager.create_template(
        name="用户试验模板",
        description="用户上传模板",
        chapters=[{"number": "1", "title": "试验目的", "sub_chapters": []}],
    )

    reloaded = TemplateManager(custom_store_path=str(store_path))
    loaded = reloaded.get_template(template.template_id)

    assert loaded is not None
    assert loaded.name == "用户试验模板"
    assert loaded.doc_type is None
    assert loaded.source_type == "uploaded_docx"


def test_template_manager_can_hide_builtin_templates(tmp_path):
    from templates.template_manager import TemplateManager

    store_path = tmp_path / "generation_templates.json"
    manager = TemplateManager(custom_store_path=str(store_path))

    assert manager.get_template("requirements") is not None
    assert manager.delete_template("requirements") is True

    reloaded = TemplateManager(custom_store_path=str(store_path))
    assert reloaded.get_template("requirements") is None
    assert all(t["id"] != "requirements" for t in reloaded.list_template_dicts())


def test_template_docx_generator_rejects_template_without_source_docx(tmp_path):
    from generators.base_generator import GeneratorFactory

    output_path = tmp_path / "generated.docx"
    generator = GeneratorFactory.create("template_docx")

    try:
        generator.generate(
            title="某型作动系统技术说明书",
            params={"template_id": "technical_specification", "inputs": {"product_name": "某型电动作动器"}},
            llm_client=FakeLLMClient(),
            output_path=str(output_path),
        )
    except ValueError as exc:
        assert "缺少原始 DOCX" in str(exc)
    else:
        raise AssertionError("无原始 DOCX 的模板不应允许生成")


def test_template_docx_generator_reports_fill_progress(tmp_path, monkeypatch):
    from generators.base_generator import GeneratorFactory
    from templates.template_manager import ChapterTemplate, DocumentTemplate

    template_path = tmp_path / "progress_template.docx"
    doc = Document()
    doc.add_heading("1 范围", level=1)
    doc.add_paragraph("NNNNN 模板正文")
    doc.save(template_path)
    output_path = tmp_path / "generated.docx"
    progress_events = []
    template = DocumentTemplate(
        template_id="progress_template",
        name="进度模板",
        description="",
        source_type="uploaded_docx",
        metadata={"source_path": str(template_path)},
        chapters=[ChapterTemplate(number="1", title="范围")],
    )

    class FakeTemplateManager:
        def get_template(self, template_id):
            return template if template_id == "progress_template" else None

    monkeypatch.setattr("templates.template_manager.TemplateManager", FakeTemplateManager)

    GeneratorFactory.create("template_docx").generate(
        title="某型作动系统需求文档",
        params={
            "template_id": "progress_template",
            "inputs": {"product_name": "某型电动作动器"},
        },
        llm_client=None,
        output_path=str(output_path),
        progress_callback=lambda current, total, chapter: progress_events.append(
            (current, total, chapter.title)
        ),
    )

    assert output_path.exists()
    assert progress_events
    assert progress_events[0][0] == 1
    assert progress_events[-1][0] == progress_events[-1][1]
    assert "某型电动作动器" in "\n".join(p.text for p in Document(output_path).paragraphs)


def test_template_docx_generator_uses_uploaded_template_styles(tmp_path, monkeypatch):
    from docx.enum.style import WD_STYLE_TYPE
    from generators.base_generator import GeneratorFactory
    from templates.template_manager import ChapterTemplate, DocumentTemplate

    template_path = tmp_path / "styled_template.docx"
    template_doc = Document()
    styles = template_doc.styles
    styles["Normal"].font.name = "Arial"
    custom_heading = styles.add_style("CustomHeadingOne", WD_STYLE_TYPE.PARAGRAPH)
    custom_heading.base_style = styles["Heading 1"]
    body_style = styles.add_style("CustomBodyText", WD_STYLE_TYPE.PARAGRAPH)
    body_style.base_style = styles["Normal"]
    template_doc.add_paragraph("1 范围", style="CustomHeadingOne")
    template_doc.add_paragraph("模板正文占位", style="CustomBodyText")
    template_doc.save(template_path)

    template = DocumentTemplate(
        template_id="styled_template",
        name="带格式模板",
        description="用于验证样式继承",
        source_type="uploaded_docx",
        metadata={"source_path": str(template_path)},
        chapters=[
            ChapterTemplate(number="1", title="范围", style_name="CustomHeadingOne", body_style_name="CustomBodyText"),
        ],
    )

    class FakeTemplateManager:
        def get_template(self, template_id):
            return template if template_id == "styled_template" else None

    monkeypatch.setattr("templates.template_manager.TemplateManager", FakeTemplateManager)

    output_path = tmp_path / "generated.docx"
    generator = GeneratorFactory.create("template_docx")
    generator.generate(
        title="样式继承验证",
        params={
            "template_id": "styled_template",
            "inputs": {"product_name": "某型电动作动器"},
        },
        llm_client=FakeLLMClient(),
        output_path=str(output_path),
    )

    generated_doc = Document(output_path)
    assert generated_doc.styles["Normal"].font.name == "Arial"
    assert generated_doc.paragraphs[0].style.name == "CustomHeadingOne"
    assert generated_doc.paragraphs[1].style.name == "CustomBodyText"
    assert "样式继承验证" not in "\n".join(p.text for p in generated_doc.paragraphs)


def test_template_docx_generator_fills_source_docx_and_removes_red_instructions(tmp_path, monkeypatch):
    from docx.shared import RGBColor
    from generators.base_generator import GeneratorFactory
    from templates.template_manager import ChapterTemplate, DocumentTemplate

    template_path = tmp_path / "fill_template.docx"
    template_doc = Document()
    template_doc.add_heading("1 目的", level=1)
    p1 = template_doc.add_paragraph()
    p1.add_run("本试验大纲规定了 XXX 项目 NNNNN 的鉴定试验程序。")
    p2 = template_doc.add_paragraph()
    p2.add_run("模板中")
    italic = p2.add_run("X 项目")
    italic.italic = True
    p2.add_run("按需修改。")
    red = template_doc.add_paragraph()
    red_run = red.add_run("【说明】红色字体说明在正式文件中删除。")
    red_run.font.color.rgb = RGBColor(255, 0, 0)
    template_doc.save(template_path)

    template = DocumentTemplate(
        template_id="fill_template",
        name="填充模板",
        description="用于验证模板原文填充",
        source_type="uploaded_docx",
        metadata={"source_path": str(template_path)},
        chapters=[
            ChapterTemplate(
                number="1",
                title="目的",
                guidance_prompt="红色字体删除，NNNNN 替换为设备名称，斜体项目按需修改。",
                template_blocks=[
                    {"type": "template_text", "text": "本试验大纲规定了 XXX 项目 NNNNN 的鉴定试验程序。"},
                    {"type": "instruction", "text": "【说明】红色字体说明在正式文件中删除。"},
                ],
                placeholders=["XXX", "NNNNN", "X 项目"],
            ),
        ],
    )

    class FakeTemplateManager:
        def get_template(self, template_id):
            return template if template_id == "fill_template" else None

    monkeypatch.setattr("templates.template_manager.TemplateManager", FakeTemplateManager)

    output_path = tmp_path / "generated.docx"
    generator = GeneratorFactory.create("template_docx")
    generator.generate(
        title="正式试验大纲",
        params={
            "template_id": "fill_template",
            "inputs": {
                "product_name": "某型电动作动器",
                "project_name": "某型电动作动器鉴定试验",
            },
        },
        llm_client=FakeLLMClient(),
        output_path=str(output_path),
    )

    generated_doc = Document(output_path)
    text = "\n".join(p.text for p in generated_doc.paragraphs)
    assert "红色字体说明" not in text
    assert "NNNNN" not in text
    assert "XXX" not in text
    assert "某型电动作动器" in text
    assert "某型电动作动器鉴定试验" in text


def test_template_docx_generator_keeps_template_table_and_removes_example_table(tmp_path, monkeypatch):
    from docx.shared import RGBColor
    from generators.base_generator import GeneratorFactory
    from templates.template_manager import ChapterTemplate, DocumentTemplate

    template_path = tmp_path / "table_template.docx"
    template_doc = Document()
    template_doc.add_heading("3 依据", level=1)
    template_doc.add_paragraph("表3-1：依据文件")
    table = template_doc.add_table(rows=2, cols=3)
    table.cell(0, 0).text = "文件编号"
    table.cell(0, 1).text = "文件名"
    table.cell(0, 2).text = "发布日期"
    table.cell(1, 0).text = "ABCC-12-R2"
    table.cell(1, 1).text = "XXX标准"
    table.cell(1, 2).text = ""
    red = template_doc.add_paragraph()
    red_run = red.add_run("【举例】")
    red_run.font.color.rgb = RGBColor(255, 0, 0)
    red_title = template_doc.add_paragraph()
    red_title_run = red_title.add_run("表3-1：依据文件")
    red_title_run.font.color.rgb = RGBColor(255, 0, 0)
    example = template_doc.add_table(rows=2, cols=3)
    example.cell(0, 0).text = "文件编号"
    example.cell(0, 1).text = "文件名"
    example.cell(0, 2).text = "发布日期"
    example.cell(1, 0).text = "D121-XXXX"
    example.cell(1, 1).text = "常见设备厂商文件"
    example.cell(1, 2).text = ""
    template_doc.save(template_path)

    template = DocumentTemplate(
        template_id="table_template",
        name="表格模板",
        description="用于验证表格处理",
        source_type="uploaded_docx",
        metadata={"source_path": str(template_path)},
        chapters=[ChapterTemplate(number="3", title="依据")],
    )

    class FakeTemplateManager:
        def get_template(self, template_id):
            return template if template_id == "table_template" else None

    monkeypatch.setattr("templates.template_manager.TemplateManager", FakeTemplateManager)

    output_path = tmp_path / "generated.docx"
    GeneratorFactory.create("template_docx").generate(
        title="正式试验大纲",
        params={
            "template_id": "table_template",
            "inputs": {
                "project_name": "某型电动作动器鉴定试验",
                "references": "GJB150A-2009 军用装备实验室环境试验方法\nQ/ABC-001 某型电动作动器产品技术条件 2026",
            },
        },
        llm_client=None,
        output_path=str(output_path),
    )

    generated_doc = Document(output_path)
    all_text = "\n".join(p.text for p in generated_doc.paragraphs)
    table_text = "\n".join(
        cell.text
        for table in generated_doc.tables
        for row in table.rows
        for cell in row.cells
    )
    assert len(generated_doc.tables) == 1
    assert "【举例】" not in all_text
    assert "常见设备厂商文件" not in table_text
    assert "GJB150A-2009" in table_text
    assert "军用装备实验室环境试验方法" in table_text
    assert "Q/ABC-001" in table_text
    assert "某型电动作动器产品技术条件" in table_text


def test_template_docx_generator_removes_plain_instruction_and_example_blocks(tmp_path, monkeypatch):
    from generators.base_generator import GeneratorFactory
    from templates.template_manager import ChapterTemplate, DocumentTemplate

    template_path = tmp_path / "plain_guidance_template.docx"
    template_doc = Document()
    template_doc.add_heading("1 目的", level=1)
    template_doc.add_paragraph("本文件规定了 NNNNN 的试验目的。")
    template_doc.add_paragraph("【说明】正式文件中删除本段。")
    template_doc.add_paragraph("1. 文中 NNNNN 替换为产品名称。")
    template_doc.add_paragraph("举例：某型设备鉴定试验大纲。")
    template_doc.add_heading("2 范围", level=1)
    template_doc.add_paragraph("NNNNN 适用于航空机载作动系统。")
    template_doc.save(template_path)

    template = DocumentTemplate(
        template_id="plain_guidance_template",
        name="非红色说明模板",
        description="用于验证非红色说明和举例",
        source_type="uploaded_docx",
        metadata={"source_path": str(template_path)},
        chapters=[
            ChapterTemplate(number="1", title="目的"),
            ChapterTemplate(number="2", title="范围"),
        ],
    )

    class FakeTemplateManager:
        def get_template(self, template_id):
            return template if template_id == "plain_guidance_template" else None

    monkeypatch.setattr("templates.template_manager.TemplateManager", FakeTemplateManager)

    output_path = tmp_path / "generated.docx"
    GeneratorFactory.create("template_docx").generate(
        title="正式试验大纲",
        params={
            "template_id": "plain_guidance_template",
            "inputs": {"product_name": "某型电动作动器"},
        },
        llm_client=None,
        output_path=str(output_path),
    )

    generated_doc = Document(output_path)
    text = "\n".join(p.text for p in generated_doc.paragraphs)
    assert "正式文件中删除" not in text
    assert "替换为产品名称" not in text
    assert "某型设备鉴定试验大纲" not in text
    assert "2 范围" in text
    assert "某型电动作动器 适用于航空机载作动系统" in text


def test_generate_document_only_skips_review_and_creates_docx(tmp_path, monkeypatch):
    from core.pipeline import generate_document_only
    from templates.template_manager import ChapterTemplate, DocumentTemplate

    template_path = tmp_path / "pipeline_template.docx"
    doc = Document()
    doc.add_paragraph("NNNNN 正式模板正文")
    doc.save(template_path)
    template = DocumentTemplate(
        template_id="pipeline_template",
        name="流水线模板",
        description="",
        source_type="uploaded_docx",
        metadata={"source_path": str(template_path)},
        chapters=[ChapterTemplate(number="1", title="范围")],
    )

    class FakeTemplateManager:
        def get_template(self, template_id):
            return template if template_id == "pipeline_template" else None

    monkeypatch.setattr("templates.template_manager.TemplateManager", FakeTemplateManager)
    progress_events = []

    result = generate_document_only(
        doc_type="pipeline_template",
        title="需求文档:测试/下载",
        params={
            "template_id": "pipeline_template",
            "inputs": {"product_name": "某型电动作动器"},
            "generator": "template_docx",
        },
        llm_client=None,
        output_dir=str(tmp_path),
        progress_callback=lambda current, total, chapter: progress_events.append(current),
    )

    assert result.status == "generated"
    assert result.generated_path
    assert "需求文档_测试_下载.docx" in result.generated_path
    assert result.review_result is None
    assert progress_events
    assert "某型电动作动器" in "\n".join(p.text for p in Document(result.generated_path).paragraphs)


def test_docx_template_parser_detects_heading_tree(tmp_path):
    from docx import Document
    from templates.docx_template_parser import DocxTemplateParser

    path = tmp_path / "template.docx"
    doc = Document()
    doc.add_heading("1 范围", level=1)
    doc.add_heading("1.1 适用范围", level=2)
    doc.add_heading("2 引用文件", level=1)
    doc.save(path)

    parsed = DocxTemplateParser().parse(str(path))

    assert parsed["name"] == "template"
    assert parsed["chapters"][0]["number"] == "1"
    assert parsed["chapters"][0]["title"] == "范围"
    assert parsed["chapters"][0]["sub_chapters"][0]["number"] == "1.1"
    assert parsed["chapters"][1]["title"] == "引用文件"


def test_docx_template_parser_extracts_guidance_and_styles(tmp_path):
    from docx.enum.style import WD_STYLE_TYPE
    from docx.shared import RGBColor
    from templates.docx_template_parser import DocxTemplateParser

    path = tmp_path / "template_guidance.docx"
    doc = Document()
    styles = doc.styles
    custom_body = styles.add_style("TemplateBody", WD_STYLE_TYPE.PARAGRAPH)
    custom_body.base_style = styles["Normal"]
    doc.add_heading("1 范围", level=1)
    doc.add_paragraph("本章应说明文档适用对象、边界和使用限制。", style="TemplateBody")
    red = doc.add_paragraph()
    red_run = red.add_run("【说明】红色字体在正式文件中删除。")
    red_run.font.color.rgb = RGBColor(255, 0, 0)
    doc.add_heading("2 引用文件", level=1)
    doc.save(path)

    parsed = DocxTemplateParser().parse(str(path))

    first = parsed["chapters"][0]
    assert first["style_name"] in ("Heading 1", "标题 1")
    assert first["body_style_name"] == "TemplateBody"
    assert "红色字体" in first["guidance_prompt"]
    assert first["template_blocks"][0]["type"] == "template_text"
    assert any(block["type"] == "instruction" for block in first["template_blocks"])


def test_docx_template_parser_extracts_example_and_table_blocks(tmp_path):
    from docx.shared import RGBColor
    from templates.docx_template_parser import DocxTemplateParser

    path = tmp_path / "template_table.docx"
    doc = Document()
    doc.add_heading("3 依据", level=1)
    doc.add_paragraph("表3-1：依据文件")
    table = doc.add_table(rows=2, cols=3)
    table.cell(0, 0).text = "文件编号"
    table.cell(0, 1).text = "文件名"
    table.cell(0, 2).text = "发布日期"
    table.cell(1, 0).text = "ABCC-12-R2"
    table.cell(1, 1).text = "XXX标准"
    red = doc.add_paragraph()
    run = red.add_run("【举例】")
    run.font.color.rgb = RGBColor(255, 0, 0)
    example_table = doc.add_table(rows=1, cols=2)
    example_table.cell(0, 0).text = "D121-XXXX"
    example_table.cell(0, 1).text = "常见设备厂商文件"
    doc.save(path)

    parsed = DocxTemplateParser().parse(str(path))
    blocks = parsed["chapters"][0]["template_blocks"]

    assert any(block["type"] == "template_table" for block in blocks)
    assert any(block["type"] == "example" for block in blocks)
    assert any(block["type"] == "example_table" for block in blocks)
    assert "举例" in parsed["chapters"][0]["guidance_prompt"]
    assert "XXX" in parsed["chapters"][0]["placeholders"]


def test_docx_template_parser_classifies_plain_guidance_markers(tmp_path):
    from templates.docx_template_parser import DocxTemplateParser

    path = tmp_path / "plain_guidance.docx"
    doc = Document()
    doc.add_heading("1 目的", level=1)
    doc.add_paragraph("本试验大纲规定了 NNNNN 的鉴定试验程序。")
    doc.add_paragraph("说明：正式文档中删除该说明段。")
    doc.add_paragraph("1. 文中 NNNNN 应替换为受试设备名称。")
    doc.add_paragraph("示例：某型产品鉴定试验大纲。")
    doc.save(path)

    parsed = DocxTemplateParser().parse(str(path))
    blocks = parsed["chapters"][0]["template_blocks"]

    assert [block["type"] for block in blocks] == [
        "template_text",
        "instruction",
        "instruction",
        "example",
    ]
    assert "正式文档中删除" in parsed["chapters"][0]["guidance_prompt"]
    assert "某型产品鉴定试验大纲" in parsed["chapters"][0]["guidance_prompt"]


def test_generate_template_api_returns_templates():
    from web.app import app

    response = app.test_client().get("/generate/api/templates")
    assert response.status_code == 200
    data = response.get_json()
    assert all((t.get("metadata") or {}).get("source_docx_path") or (t.get("metadata") or {}).get("source_path")
               for t in data["templates"])


def test_template_library_page_and_api_load():
    from web.app import app

    page = app.test_client().get("/template-library/")
    response = app.test_client().get("/template-library/api/templates")

    assert page.status_code == 200
    assert "生成模板库".encode("utf-8") in page.data
    assert response.status_code == 200
    assert "templates" in response.get_json()


def test_template_library_parse_saves_source_docx_asset(tmp_path):
    from io import BytesIO
    from pathlib import Path
    from web.app import app

    doc = Document()
    doc.add_heading("1 范围", level=1)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    response = app.test_client().post(
        "/template-library/api/parse",
        data={"file": (buffer, "asset_template.docx")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["id"].startswith("template_")
    source_path = Path(app.root_path).parent / data["metadata"]["source_docx_path"]
    assert source_path.exists()
    assert source_path.name == "source.docx"


def test_generate_start_requires_product_name():
    from web.app import app

    response = app.test_client().post(
        "/generate/start",
        data=json.dumps({
            "template_id": "requirements",
            "title": "需求文档",
            "inputs": {},
        }),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "产品名称" in response.get_json()["error"]


def test_generate_record_delete_api():
    from web.app import app

    db = app.db
    task_id = db.create_generate_task(
        doc_type="template_test",
        template_name="测试模板",
        params={"title": "测试生成记录"},
    )
    db.update_generate_task(task_id, status="completed", progress=100, result_path="")

    response = app.test_client().delete(f"/generate/delete/{task_id}")

    assert response.status_code == 200
    assert response.get_json()["deleted"] == 1
    assert db.get_generate_task(task_id) is None


def test_generate_recent_api_paginates_and_decorates_status():
    from web.app import app

    db = app.db
    task_ids = []
    for index in range(6):
        task_id = db.create_generate_task(
            doc_type=f"template_page_{index}",
            template_name=f"分页模板 {index}",
            params={"title": f"分页记录 {index}"},
        )
        db.update_generate_task(
            task_id,
            status="completed" if index % 2 == 0 else "failed",
            progress=100,
            result_path=f"generated_{index}.docx" if index % 2 == 0 else "",
            error="生成失败" if index % 2 else "",
        )
        task_ids.append(task_id)

    response = app.test_client().get("/generate/api/recent?page=2")

    assert response.status_code == 200
    data = response.get_json()
    assert data["pagination"]["page_size"] == 5
    assert data["pagination"]["page"] >= 1
    assert data["pagination"]["total"] >= 6
    assert len(data["tasks"]) <= 5
    assert all("status_label" in task for task in data["tasks"])
    assert all("badge_class" in task for task in data["tasks"])

    for task_id in task_ids:
        db.delete_generate_task(task_id)


def test_running_generate_record_cannot_be_deleted():
    from web.app import app

    db = app.db
    task_id = db.create_generate_task(
        doc_type="template_test",
        template_name="测试模板",
        params={"title": "运行中生成记录"},
    )
    db.update_generate_task(task_id, status="processing", progress=20)

    response = app.test_client().delete(f"/generate/delete/{task_id}")

    assert response.status_code == 400
    assert "仍在执行" in response.get_json()["error"]
    assert db.get_generate_task(task_id) is not None
    db.delete_generate_task(task_id)
