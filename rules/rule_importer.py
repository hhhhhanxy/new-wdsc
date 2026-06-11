"""Parse and validate the user-facing rule import workbook."""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from io import BytesIO
from pathlib import PurePosixPath
import re
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape


NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


HEADER_ALIASES = {
    "规则编号": "code",
    "规则名称": "name",
    "检查要求": "logic",
    "规则说明": "description",
    "审查方式": "review_type",
    "问题级别": "severity",
    "检查范围": "scope",
    "目标章节": "target_headings",
    "必须包含的内容": "required_elements",
    "依据文件/条款": "standard_ref",
    "检查类型仅规则引擎": "check_type",
    "字段名称仅规则引擎": "field_labels",
    "匹配方式仅规则引擎": "match_mode",
    "匹配内容仅规则引擎": "match_value",
}

REQUIRED_FIELDS = {
    "code": "规则编号",
    "name": "规则名称",
    "logic": "检查要求",
    "review_type": "审查方式",
    "severity": "问题级别",
    "scope": "检查范围",
}
FIELD_LABELS = {
    **REQUIRED_FIELDS,
    "check_type": "检查类型",
    "field_labels": "字段名称",
    "match_mode": "匹配方式",
    "match_value": "匹配内容",
}

REVIEW_TYPE_MAP = {"LLM": "llm", "规则引擎": "rule"}
SEVERITY_MAP = {"错误": "error", "警告": "warning", "信息": "info"}
SCOPE_MAP = {"全文": "all", "封面": "cover", "签署页": "signature", "前言": "preface", "正文": "body"}
CHECK_TYPE_MAP = {"表格字段格式检查": "table_field_regex"}
MATCH_MODE_MAP = {"开头是": "starts_with", "结尾是": "ends_with", "包含": "contains", "完全等于": "equals"}


class RuleImportError(ValueError):
    """Raised when the workbook structure cannot be parsed."""


@dataclass
class ImportedRuleRow:
    row_number: int
    raw: dict[str, str]
    locations: dict[str, str] = field(default_factory=dict)
    payload: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    error_details: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    action: str = "create"
    existing_rule_id: str = ""
    changes: list[str] = field(default_factory=list)
    change_details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_number": self.row_number,
            "code": self.raw.get("code", ""),
            "name": self.raw.get("name", ""),
            "review_type": self.raw.get("review_type", ""),
            "errors": self.errors,
            "error_details": self.error_details,
            "warnings": self.warnings,
            "action": self.action,
            "changes": self.changes,
            "change_details": self.change_details,
            "raw": self.raw,
            "payload": self.payload or {},
            "valid": not self.errors,
            "importable": not self.errors and self.action in {"create", "update"},
        }

    def add_error(self, field_name: str, message: str) -> None:
        cell = self.locations.get(field_name, f"第{self.row_number}行")
        label = FIELD_LABELS.get(field_name, field_name)
        self.error_details.append({"cell": cell, "field": label, "message": message})
        self.errors.append(f"{cell} {label}：{message}")


def _clean_header(value: str) -> str:
    return "".join(str(value or "").replace("*", "").split())


def _column_index(reference: str) -> int:
    letters = "".join(ch for ch in reference if ch.isalpha()).upper()
    result = 0
    for letter in letters:
        result = result * 26 + ord(letter) - 64
    return result - 1


def _xml_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(text.text or "" for text in node.iter(f"{{{NS_MAIN}}}t"))


def _shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [_xml_text(item) for item in root.findall(f"{{{NS_MAIN}}}si")]


def _worksheet_path(archive: ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{{{NS_REL_PKG}}}Relationship")
    }
    sheets = workbook.find(f"{{{NS_MAIN}}}sheets")
    if sheets is None:
        raise RuleImportError("Excel 中没有可读取的工作表")

    selected = None
    for sheet in sheets:
        if sheet.attrib.get("name") == sheet_name:
            selected = sheet
            break
    if selected is None:
        selected = next(iter(sheets), None)
    if selected is None:
        raise RuleImportError("Excel 中没有可读取的工作表")

    rel_id = selected.attrib.get(f"{{{NS_REL_DOC}}}id")
    target = targets.get(rel_id or "")
    if not target:
        raise RuleImportError("无法定位 Excel 工作表")
    if target.startswith("/"):
        return target.lstrip("/")
    return str(PurePosixPath("xl") / target)


def _read_rows(file_bytes: bytes, sheet_name: str = "规则导入") -> list[tuple[int, list[str]]]:
    try:
        with ZipFile(BytesIO(file_bytes)) as archive:
            shared = _shared_strings(archive)
            path = _worksheet_path(archive, sheet_name)
            root = ET.fromstring(archive.read(path))
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise RuleImportError("文件不是有效的 .xlsx Excel 文件") from exc

    result: list[tuple[int, list[str]]] = []
    sheet_data = root.find(f"{{{NS_MAIN}}}sheetData")
    if sheet_data is None:
        return result

    for row in sheet_data.findall(f"{{{NS_MAIN}}}row"):
        row_number = int(row.attrib.get("r", len(result) + 1))
        values: dict[int, str] = {}
        max_index = -1
        for cell in row.findall(f"{{{NS_MAIN}}}c"):
            index = _column_index(cell.attrib.get("r", "A1"))
            cell_type = cell.attrib.get("t", "")
            value_node = cell.find(f"{{{NS_MAIN}}}v")
            if cell_type == "inlineStr":
                value = _xml_text(cell.find(f"{{{NS_MAIN}}}is"))
            elif value_node is None:
                value = ""
            elif cell_type == "s":
                try:
                    value = shared[int(value_node.text or "0")]
                except (ValueError, IndexError):
                    value = ""
            else:
                value = value_node.text or ""
            values[index] = str(value).strip()
            max_index = max(max_index, index)
        result.append((row_number, [values.get(i, "") for i in range(max_index + 1)]))
    return result


def parse_rule_workbook(file_bytes: bytes) -> list[ImportedRuleRow]:
    rows = _read_rows(file_bytes)
    header_index = None
    column_map: dict[int, str] = {}
    for index, (_, values) in enumerate(rows[:20]):
        candidate = {
            column: HEADER_ALIASES[_clean_header(value)]
            for column, value in enumerate(values)
            if _clean_header(value) in HEADER_ALIASES
        }
        if {"code", "name", "logic"}.issubset(candidate.values()):
            header_index = index
            column_map = candidate
            break

    if header_index is None:
        raise RuleImportError("未找到规则表头，请使用平台下载的导入模板")
    missing_headers = [label for key, label in REQUIRED_FIELDS.items() if key not in column_map.values()]
    if missing_headers:
        raise RuleImportError(f"模板缺少必需列：{'、'.join(missing_headers)}")

    parsed: list[ImportedRuleRow] = []
    for row_number, values in rows[header_index + 1:]:
        raw = {
            field_name: values[column].strip() if column < len(values) else ""
            for column, field_name in column_map.items()
        }
        if not any(raw.values()):
            continue
        locations = {
            field_name: f"{_excel_column(column + 1)}{row_number}"
            for column, field_name in column_map.items()
        }
        parsed.append(ImportedRuleRow(row_number=row_number, raw=raw, locations=locations))
    return parsed


def validate_import_rows(
    rows: list[ImportedRuleRow],
    source: str,
    existing_rules: dict[str, dict[str, Any]] | set[str],
    validate_payload,
    duplicate_mode: str = "reject",
) -> list[ImportedRuleRow]:
    seen_codes: set[str] = set()
    if isinstance(existing_rules, set):
        existing_map = {code.strip().lower(): {"code": code} for code in existing_rules if code.strip()}
    else:
        existing_map = {code.strip().lower(): value for code, value in existing_rules.items() if code.strip()}
    prior_texts: list[tuple[str, str, str]] = [
        (
            str(info.get("code", "")),
            str(info.get("name", "")),
            str(info.get("logic", "")),
        )
        for info in existing_map.values()
    ]

    for row in rows:
        raw = row.raw
        for field_name, label in REQUIRED_FIELDS.items():
            if not raw.get(field_name, "").strip():
                row.add_error(field_name, "不能为空")

        code = raw.get("code", "").strip()
        normalized_code = code.lower()
        if normalized_code in seen_codes:
            row.add_error("code", "在本文件中重复")
        if normalized_code:
            seen_codes.add(normalized_code)

        review_type = REVIEW_TYPE_MAP.get(raw.get("review_type", "").strip())
        severity = SEVERITY_MAP.get(raw.get("severity", "").strip())
        scope = SCOPE_MAP.get(raw.get("scope", "").strip())
        if raw.get("review_type") and not review_type:
            row.add_error("review_type", "只能填写 LLM 或规则引擎")
        if raw.get("severity") and not severity:
            row.add_error("severity", "只能填写错误、警告或信息")
        if raw.get("scope") and not scope:
            row.add_error("scope", "只能填写全文、封面、签署页、前言或正文")

        params: dict[str, Any] = {}
        if review_type == "rule":
            check_type = CHECK_TYPE_MAP.get(raw.get("check_type", "").strip())
            match_mode = MATCH_MODE_MAP.get(raw.get("match_mode", "").strip())
            field_labels = raw.get("field_labels", "").strip()
            match_value = raw.get("match_value", "").strip()
            if not check_type:
                row.add_error("check_type", "规则引擎需要选择表格字段格式检查")
            if not field_labels:
                row.add_error("field_labels", "规则引擎需要填写")
            if not match_mode:
                row.add_error("match_mode", "规则引擎需要选择")
            if not match_value:
                row.add_error("match_value", "规则引擎需要填写")
            params = {
                "check_type": check_type or "",
                "field_labels": field_labels,
                "match_mode": match_mode or "",
                "match_value": match_value,
            }

        payload = {
            "source": source,
            "name": raw.get("name", "").strip(),
            "description": raw.get("description", "").strip(),
            "code": code,
            "logic": raw.get("logic", "").strip(),
            "review_type": review_type or "",
            "severity": severity or "",
            "scope": scope or "",
            "standard_ref": raw.get("standard_ref", "").strip(),
            "target_headings": raw.get("target_headings", "").strip(),
            "required_elements": raw.get("required_elements", "").strip(),
            "enabled": True,
            "params": params,
        }
        existing = existing_map.get(normalized_code)
        if existing:
            row.existing_rule_id = str(existing.get("rule_id", ""))
            if duplicate_mode == "skip":
                row.action = "skip"
                row.warnings.append("规则编号已存在，本次将跳过")
            elif duplicate_mode == "update":
                if existing.get("source") != source:
                    row.add_error("code", "已属于其他规则集，不能更新")
                elif not existing.get("custom"):
                    row.add_error("code", "对应内置规则，不能通过 Excel 更新")
                else:
                    row.action = "update"
                    payload["enabled"] = bool(existing.get("enabled", True))
                    comparable = {
                        "name": "规则名称",
                        "description": "规则说明",
                        "logic": "检查要求",
                        "review_type": "审查方式",
                        "severity": "问题级别",
                        "scope": "检查范围",
                        "standard_ref": "依据文件/条款",
                        "target_headings": "目标章节",
                        "required_elements": "必须包含的内容",
                        "params": "规则引擎参数",
                    }
                    row.change_details = [
                        {
                            "field": label,
                            "before": existing.get(key),
                            "after": payload.get(key),
                        }
                        for key, label in comparable.items()
                        if _comparison_value(existing.get(key)) != _comparison_value(payload.get(key))
                    ]
                    row.changes = [item["field"] for item in row.change_details]
                    if not row.changes:
                        row.action = "skip"
                        row.warnings.append("规则内容没有变化，本次将跳过")
            else:
                row.add_error("code", "已存在")

        if not row.errors:
            validation_error = validate_payload(payload)
            if validation_error:
                row.add_error("logic", validation_error)
        if not row.errors:
            row.payload = payload
            _add_quality_warnings(row, prior_texts)
            prior_texts.append((code, payload["name"], payload["logic"]))
    return rows


def _comparison_value(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and re.search(r"[,，;；\n]", value):
        return [item.strip() for item in re.split(r"[,，;；\n]+", value) if item.strip()]
    return value


def _add_quality_warnings(row: ImportedRuleRow, prior_texts: list[tuple[str, str, str]]) -> None:
    payload = row.payload or {}
    name = payload.get("name", "")
    logic = payload.get("logic", "")
    if len(name) < 4 or name in {"格式检查", "内容检查", "规则检查", "完整性检查"}:
        row.warnings.append("规则名称过于笼统，建议写明检查对象")
    if len(logic) < 20:
        row.warnings.append("检查要求过短，建议补充检查对象、通过条件和不通过条件")
    decision_terms = ("通过", "不通过", "否则", "缺少", "必须", "应当", "应", "不得", "不符合")
    if not any(term in logic for term in decision_terms):
        row.warnings.append("检查要求缺少明确判定条件")
    vague_terms = ("合理", "适当", "相关内容", "符合要求", "视情况")
    if any(term in logic for term in vague_terms):
        row.warnings.append("检查要求含有模糊表述，建议改为可验证条件")
    for prior_code, prior_name, prior_logic in prior_texts:
        name_ratio = SequenceMatcher(None, name, prior_name).ratio() if name and prior_name else 0
        logic_ratio = SequenceMatcher(None, logic, prior_logic).ratio() if logic and prior_logic else 0
        if max(name_ratio, logic_ratio) >= 0.9:
            row.warnings.append(f"与规则 {prior_code or prior_name} 高度相似，请确认是否重复")
            break


def build_issue_workbook(rows: list[ImportedRuleRow]) -> bytes:
    """Build a small correction workbook containing invalid or warning rows."""
    headers = [
        "Excel 行", "规则编号", "规则名称", "检查要求", "规则说明", "审查方式",
        "问题级别", "检查范围", "目标章节", "必须包含的内容", "依据文件/条款",
        "检查类型", "字段名称", "匹配方式", "匹配内容",
        "错误单元格", "错误字段", "错误原因", "质量提醒",
    ]
    field_order = [
        "code", "name", "logic", "description", "review_type", "severity", "scope",
        "target_headings", "required_elements", "standard_ref", "check_type",
        "field_labels", "match_mode", "match_value",
    ]
    values = [headers]
    for row in rows:
        if not row.errors and not row.warnings:
            continue
        values.append([
            row.row_number,
            *[row.raw.get(field, "") for field in field_order],
            "；".join(detail["cell"] for detail in row.error_details),
            "；".join(detail["field"] for detail in row.error_details),
            "；".join(detail["message"] for detail in row.error_details),
            "；".join(row.warnings),
        ])

    rows_xml = []
    for row_number, values_row in enumerate(values, 1):
        cells = []
        for column, value in enumerate(values_row, 1):
            reference = f"{_excel_column(column)}{row_number}"
            cells.append(
                f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value or ""))}</t></is></c>'
            )
        rows_xml.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS_MAIN}"><sheetData>{"".join(rows_xml)}</sheetData></worksheet>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL_DOC}">'
        '<sheets><sheet name="导入问题" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{NS_REL_PKG}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{NS_REL_PKG}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return output.getvalue()


def _excel_column(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result
