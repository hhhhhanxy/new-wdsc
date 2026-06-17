import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const rootDir = path.resolve("..");
const templatePath = path.join(rootDir, "outputs", "rule-import-template", "面向用户的审查规则导入模板.xlsx");
const overridesPath = path.join(rootDir, "config", "rule_overrides.json");
const outputDir = path.join(rootDir, "outputs", "rule-import-template");
const previewDir = path.join(outputDir, "x-product-previews");
const outputPath = path.join(outputDir, "X产品规范检查-规则导入模板.xlsx");

const reviewTypeLabels = {
  llm: "LLM",
  rule: "规则引擎",
  both: "规则+LLM",
};
const severityLabels = {
  error: "错误",
  warning: "警告",
  info: "信息",
};
const scopeLabels = {
  all: "全文",
  cover: "封面",
  signature: "签署页",
  preface: "前言",
  body: "正文",
};
const matchModeLabels = {
  starts_with: "开头是",
  ends_with: "结尾是",
  contains: "包含",
  equals: "完全等于",
};

function valueOf(value) {
  return value && typeof value === "object" && !Array.isArray(value) && Object.prototype.hasOwnProperty.call(value, "value")
    ? value.value
    : value;
}

function listText(value) {
  const plain = valueOf(value);
  if (Array.isArray(plain)) return plain.filter(Boolean).join("；");
  return String(plain || "");
}

function tableFieldParams(params = {}) {
  const checkType = valueOf(params.check_type);
  if (checkType !== "table_field_regex") {
    return ["", "", "", ""];
  }
  return [
    "表格字段格式检查",
    listText(params.field_labels),
    matchModeLabels[valueOf(params.match_mode)] || "",
    String(valueOf(params.match_value) || ""),
  ];
}

const overrides = JSON.parse(await fs.readFile(overridesPath, "utf8"));
const productRules = Object.values(overrides)
  .filter((rule) => rule.source === "product_rules")
  .sort((a, b) => String(a.code || "").localeCompare(String(b.code || ""), "zh-Hans-CN", { numeric: true }));

const rows = productRules.map((rule, index) => {
  const [checkType, fieldLabels, matchMode, matchValue] = tableFieldParams(rule.params || {});
  return [
    index + 1,
    rule.code || "",
    rule.name || "",
    rule.logic || "",
    rule.description || "",
    reviewTypeLabels[rule.review_type] || "LLM",
    severityLabels[rule.severity] || "警告",
    scopeLabels[rule.scope] || "全文",
    listText(rule.target_headings),
    listText(rule.required_elements),
    rule.standard_ref || "",
    checkType,
    fieldLabels,
    matchMode,
    matchValue,
  ];
});

const blob = await FileBlob.load(templatePath);
const wb = await SpreadsheetFile.importXlsx(blob);
const sheet = wb.worksheets.getItem("规则导入");

sheet.getRange("A6:O105").clear({ applyTo: "contents" });
if (rows.length) {
  sheet.getRangeByIndexes(5, 0, rows.length, 15).values = rows;
}
sheet.getRange(`A6:P${5 + Math.max(rows.length, 1)}`).format.rowHeightPx = 70;
sheet.getRange("A1:P1").values = [["X产品规范检查 - 审查规则批量导入"]];
sheet.getRange("A2:P2").values = [[
  "已整理当前平台中“X产品规范检查”规则集的 P-001 至 P-006 规则。可直接在规则管理中导入；若规则编号已存在，请选择更新或跳过重复规则。"
]];

await fs.mkdir(previewDir, { recursive: true });
const rendered = await wb.render({ sheetName: "规则导入", range: "A1:P15", scale: 1, format: "png" });
await fs.writeFile(path.join(previewDir, "规则导入.png"), new Uint8Array(await rendered.arrayBuffer()));

const inspection = await wb.inspect({
  kind: "table",
  range: "规则导入!A5:P12",
  include: "values,formulas",
  tableMaxRows: 8,
  tableMaxCols: 16,
  maxChars: 6000,
});
await fs.writeFile(path.join(outputDir, "x-product-inspection.ndjson"), inspection.ndjson, "utf8");

const errors = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
await fs.writeFile(path.join(outputDir, "x-product-formula-errors.ndjson"), errors.ndjson, "utf8");

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(outputPath);
console.log(outputPath);
