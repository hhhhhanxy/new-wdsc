import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve("../outputs/rule-import-template");
const outputPath = path.join(outputDir, "面向用户的审查规则导入模板.xlsx");
const previewDir = path.join(outputDir, "user-previews");

const wb = Workbook.create();
const input = wb.worksheets.add("规则导入");
const guide = wb.worksheets.add("怎么填写");
const examples = wb.worksheets.add("填写示例");

const c = {
  navy: "#17365D",
  blue: "#2F75B5",
  lightBlue: "#DDEBF7",
  green: "#70AD47",
  lightGreen: "#E2F0D9",
  orange: "#ED7D31",
  lightOrange: "#FCE4D6",
  gray: "#E7E6E6",
  lightGray: "#F5F6F7",
  border: "#B4C6D7",
  text: "#263238",
  red: "#C00000",
  lightRed: "#F4CCCC",
  white: "#FFFFFF",
};

function title(sheet, endColumn, text, subtitle) {
  sheet.mergeCells(`A1:${endColumn}1`);
  sheet.getRange(`A1:${endColumn}1`).values = [[text]];
  sheet.getRange(`A1:${endColumn}1`).format = {
    fill: c.navy,
    font: { color: c.white, bold: true, size: 18 },
    verticalAlignment: "center",
  };
  sheet.getRange("1:1").format.rowHeightPx = 42;

  sheet.mergeCells(`A2:${endColumn}2`);
  sheet.getRange(`A2:${endColumn}2`).values = [[subtitle]];
  sheet.getRange(`A2:${endColumn}2`).format = {
    fill: c.lightBlue,
    font: { color: c.text, size: 10 },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("2:2").format.rowHeightPx = 32;
}

function styleHeader(range, fill = c.blue) {
  range.format = {
    fill,
    font: { color: c.white, bold: true, size: 10 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", color: c.border, style: "thin" },
  };
}

function styleBody(range, fill = c.white) {
  range.format = {
    fill,
    font: { color: c.text, size: 10 },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", color: c.border, style: "thin" },
  };
}

// Main input sheet
title(
  input,
  "P",
  "审查规则批量导入",
  "从第 6 行开始填写，一行一条规则。带 * 的列必须填写；浅橙色列仅在选择“规则引擎”时填写。"
);
input.showGridLines = false;
input.mergeCells("A4:P4");
input.getRange("A4:P4").values = [[
  "推荐优先使用 LLM：适合内容完整性、语义、一致性等检查。只有检查表格字段固定格式时，才选择规则引擎。"
]];
input.getRange("A4:P4").format = {
  fill: c.lightGreen,
  font: { color: "#385723", bold: true },
  wrapText: true,
  verticalAlignment: "center",
  borders: { preset: "all", color: c.border, style: "thin" },
};

const headers = [
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
];
input.getRange("A5:P5").values = [headers];
styleHeader(input.getRange("A5:K5"));
styleHeader(input.getRange("L5:O5"), c.orange);
styleHeader(input.getRange("P5:P5"), "#7F8C8D");
input.getRange("5:5").format.rowHeightPx = 42;

const rows = 100;
input.getRange(`A6:P${5 + rows}`).values = Array.from({ length: rows }, (_, i) => [
  i + 1, "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
]);
styleBody(input.getRange(`A6:P${5 + rows}`));
input.getRange(`L6:O${5 + rows}`).format.fill = "#FFF2CC";
input.getRange(`P6:P${5 + rows}`).format.fill = c.lightGray;
input.getRange(`A6:A${5 + rows}`).format.horizontalAlignment = "center";
input.getRange(`F6:H${5 + rows}`).format.horizontalAlignment = "center";
input.getRange(`L6:P${5 + rows}`).format.horizontalAlignment = "center";

input.getRange("P6").formulas = [[
  '=IF(B6&C6&D6&E6&F6&G6&H6&I6&J6&K6&L6&M6&N6&O6="","",IF(OR(B6="",C6="",D6="",F6="",G6="",H6=""),"请补必填项",IF(AND(F6="规则引擎",OR(L6="",M6="",N6="",O6="")),"请补引擎参数","可以导入")))'
]];
input.getRange(`P6:P${5 + rows}`).fillDown();

input.getRange(`F6:F${5 + rows}`).dataValidation = {
  rule: { type: "list", values: ["LLM", "规则引擎"] },
};
input.getRange(`G6:G${5 + rows}`).dataValidation = {
  rule: { type: "list", values: ["错误", "警告", "信息"] },
};
input.getRange(`H6:H${5 + rows}`).dataValidation = {
  rule: { type: "list", values: ["全文", "封面", "签署页", "前言", "正文"] },
};
input.getRange(`L6:L${5 + rows}`).dataValidation = {
  rule: { type: "list", values: ["", "表格字段格式检查"] },
};
input.getRange(`N6:N${5 + rows}`).dataValidation = {
  rule: { type: "list", values: ["", "开头是", "结尾是", "包含", "完全等于"] },
};

input.getRange(`P6:P${5 + rows}`).conditionalFormats.add("containsText", {
  text: "可以导入",
  format: { fill: c.lightGreen, font: { color: "#385723", bold: true } },
});
input.getRange(`P6:P${5 + rows}`).conditionalFormats.add("containsText", {
  text: "请补",
  format: { fill: c.lightRed, font: { color: c.red, bold: true } },
});

const widths = [50, 95, 150, 310, 190, 95, 90, 90, 150, 180, 210, 140, 160, 100, 120, 110];
widths.forEach((width, index) => input.getRangeByIndexes(0, index, rows + 5, 1).format.columnWidthPx = width);
input.getRange(`6:${5 + rows}`).format.rowHeightPx = 44;
input.freezePanes.freezeRows(5);
input.freezePanes.freezeColumns(4);
const inputTable = input.tables.add(`A5:P${5 + rows}`, true, "UserRuleImportTable");
inputTable.style = "TableStyleMedium2";

// Compact guide
title(
  guide,
  "F",
  "怎么填写",
  "先在平台进入目标规则集，再填写 6 个核心字段。其他字段可暂时留空；导入后的规则默认开启。"
);
guide.showGridLines = false;
guide.getRange("A4:F4").values = [["填写顺序", "字段", "是否必填", "怎么写", "简单示例", "注意"]];
styleHeader(guide.getRange("A4:F4"));
const guideRows = [
  ["1", "规则编号", "必填", "使用稳定且不重复的编号", "T-001", "不要与已有规则编号重复"],
  ["2", "规则名称", "必填", "用一句短语说明检查什么", "试验项目范围完整性检查", "一条规则尽量只检查一个核心问题"],
  ["3", "检查要求", "必填", "写清检查对象、通过条件和不通过条件", "“范围”章节必须包含温度、高度、温度变化和湿热，缺少任一项时报错", "不要只写“检查是否合理”"],
  ["4", "审查方式", "必填", "一般内容检查选 LLM；表格固定格式检查选规则引擎", "LLM", "不确定时优先选 LLM"],
  ["5", "问题级别", "必填", "关键问题选错误；需确认选警告；优化提示选信息", "警告", "不要全部设置为错误"],
  ["6", "检查范围", "必填", "选择规则实际作用的位置", "正文", "尽量不要无条件选择全文"],
];
guide.getRange("A5:F10").values = guideRows;
styleBody(guide.getRange("A5:F10"));
guide.getRange("C5:C10").format.horizontalAlignment = "center";
guide.getRange("A5:A10").format.horizontalAlignment = "center";
guide.getRange("A5:F10").format.rowHeightPx = 56;

guide.mergeCells("A14:F14");
guide.getRange("A14:F14").values = [["选填字段什么时候用"]];
guide.getRange("A14:F14").format = {
  fill: c.blue,
  font: { color: c.white, bold: true, size: 11 },
  verticalAlignment: "center",
};
guide.getRange("A15:F19").values = [
  ["目标章节", "只想检查某些章节时填写，多个章节用中文分号“；”分隔", "范围；试验项目", "", "", ""],
  ["必须包含的内容", "检查章节完整性时填写，多个内容用中文分号“；”分隔", "温度；高度；温度变化；湿热", "", "", ""],
  ["依据文件/条款", "有明确标准或内部文件依据时填写", "GJB XXXX-XXXX 第 5.2 条", "", "", ""],
  ["规则说明", "补充规则目的、风险或适用场景", "用于检查自然环境类鉴定试验覆盖情况", "", "", ""],
  ["浅橙色参数", "只有审查方式选择“规则引擎”时才填写", "字段名称=阶段标识；匹配方式=结尾是；匹配内容=-AB", "", "", ""],
];
for (let r = 15; r <= 19; r++) guide.mergeCells(`B${r}:F${r}`);
styleBody(guide.getRange("A15:F19"));
guide.getRange("A20:F21").merge();
guide.getRange("A20:F21").values = [[
  "导入前建议：先用 3-5 条典型规则试审。导入后的规则默认开启，Excel 中的空白行不会被导入。"
]];
guide.getRange("A20:F21").format = {
  fill: c.lightOrange,
  font: { color: "#7F4125", bold: true },
  wrapText: true,
  verticalAlignment: "center",
  borders: { preset: "all", color: c.orange, style: "thin" },
};
[80, 125, 90, 330, 250, 235].forEach((width, index) => guide.getRangeByIndexes(0, index, 21, 1).format.columnWidthPx = width);
guide.freezePanes.freezeRows(4);

// Examples
title(
  examples,
  "P",
  "填写示例",
  "这里只展示两类常用规则：内容类规则和表格格式规则。请根据实际要求改写，不要原样导入。"
);
examples.showGridLines = false;
examples.getRange("A5:P5").values = [headers];
styleHeader(examples.getRange("A5:K5"));
styleHeader(examples.getRange("L5:O5"), c.orange);
styleHeader(examples.getRange("P5:P5"), "#7F8C8D");
examples.getRange("5:5").format.rowHeightPx = 42;
examples.getRange("A6:P7").values = [
  [
    1,
    "T-001",
    "试验项目范围完整性检查",
    "检查“范围”或“试验项目”章节。正文必须明确包含温度、高度、温度变化、湿热等自然环境类鉴定试验；全部包含时通过，缺少任一项时指出缺失内容，不得编造试验数据。",
    "用于检查试验大纲是否覆盖规定的自然环境试验项目。",
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
    "可以导入",
  ],
  [
    2,
    "P-006",
    "阶段标识格式检查",
    "检查封面表格中的“阶段标识”或“审查阶段标识”。字段值以“-AB”结尾时通过，否则指出实际值和期望格式。",
    "用于检查封面阶段标识是否符合项目命名规范。",
    "规则引擎",
    "警告",
    "封面",
    "",
    "",
    "项目文档编码规则第 4.2 条",
    "表格字段格式检查",
    "阶段标识；审查阶段标识",
    "结尾是",
    "-AB",
    "可以导入",
  ],
];
styleBody(examples.getRange("A6:P7"));
examples.getRange("L6:O7").format.fill = "#FFF2CC";
examples.getRange("P6:P7").format.fill = c.lightGreen;
examples.getRange("P6:P7").format.font = { color: "#385723", bold: true };
examples.getRange("6:7").format.rowHeightPx = 110;
widths.forEach((width, index) => examples.getRangeByIndexes(0, index, 7, 1).format.columnWidthPx = width);
examples.freezePanes.freezeRows(5);
examples.freezePanes.freezeColumns(4);
const exampleTable = examples.tables.add("A5:P7", true, "UserRuleExampleTable");
exampleTable.style = "TableStyleMedium2";

await fs.mkdir(previewDir, { recursive: true });
for (const [sheetName, range] of [
  ["规则导入", "A1:P15"],
  ["怎么填写", "A1:F21"],
  ["填写示例", "A1:P7"],
]) {
  const rendered = await wb.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await rendered.arrayBuffer()));
}

const inspection = await wb.inspect({
  kind: "table",
  range: "规则导入!A1:P10",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 16,
  maxChars: 6000,
});
await fs.writeFile(path.join(outputDir, "user-inspection.ndjson"), inspection.ndjson, "utf8");

const errors = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
await fs.writeFile(path.join(outputDir, "user-formula-errors.ndjson"), errors.ndjson, "utf8");

const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(outputPath);
console.log(outputPath);
