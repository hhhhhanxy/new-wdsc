import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve("../outputs/rule-import-template");
const outputPath = path.join(outputDir, "审查规则批量导入模板.xlsx");
const previewDir = path.join(outputDir, "previews");

const wb = Workbook.create();
const guide = wb.worksheets.add("填写说明");
const rules = wb.worksheets.add("规则填写模板");
const sets = wb.worksheets.add("规则集定义");
const fields = wb.worksheets.add("字段说明");
const examples = wb.worksheets.add("填写示例");
const enums = wb.worksheets.add("枚举与规范");

const colors = {
  navy: "#17365D",
  blue: "#2F75B5",
  sky: "#DDEBF7",
  paleBlue: "#EAF3F8",
  green: "#70AD47",
  paleGreen: "#E2F0D9",
  orange: "#F4B183",
  paleOrange: "#FCE4D6",
  red: "#C00000",
  paleRed: "#F4CCCC",
  gray: "#E7E6E6",
  paleGray: "#F3F5F7",
  border: "#B4C6D7",
  text: "#1F2937",
  white: "#FFFFFF",
};

function title(sheet, range, text, subtitle = "") {
  sheet.mergeCells(range);
  const cell = sheet.getRange(range);
  cell.values = [[text]];
  cell.format = {
    fill: colors.navy,
    font: { bold: true, color: colors.white, size: 18 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  cell.format.rowHeightPx = 42;
  if (subtitle) {
    const row = Number(range.match(/\d+/)?.[0] ?? 1) + 1;
    const endCol = range.split(":")[1].replace(/\d+/g, "");
    sheet.mergeCells(`A${row}:${endCol}${row}`);
    const sub = sheet.getRange(`A${row}:${endCol}${row}`);
    sub.values = [[subtitle]];
    sub.format = {
      fill: colors.paleBlue,
      font: { color: colors.text, size: 10 },
      wrapText: true,
      verticalAlignment: "center",
    };
    sub.format.rowHeightPx = 34;
  }
}

function header(range, fill = colors.blue) {
  range.format = {
    fill,
    font: { bold: true, color: colors.white, size: 10 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", color: colors.border, style: "thin" },
  };
  range.format.rowHeightPx = 34;
}

function body(range, fill = colors.white) {
  range.format = {
    fill,
    font: { color: colors.text, size: 10 },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", color: colors.border, style: "thin" },
  };
}

function section(sheet, range, text) {
  sheet.mergeCells(range);
  const r = sheet.getRange(range);
  r.values = [[text]];
  r.format = {
    fill: colors.blue,
    font: { bold: true, color: colors.white, size: 11 },
    verticalAlignment: "center",
  };
  r.format.rowHeightPx = 27;
}

// 填写说明
title(
  guide,
  "A1:H1",
  "审查规则批量整理与导入模板",
  "依据当前平台“新建规则”表单与后端校验整理。带 * 的字段为必填；带“条件必填”的字段仅在特定审查方式下必填。"
);
guide.showGridLines = false;
section(guide, "A4:H4", "使用流程");
guide.getRange("A5:H9").values = [
  ["步骤", "操作", "说明", "", "", "", "", ""],
  ["1", "先维护规则集", "在“规则集定义”中填写规则集编码、名称和说明。规则填写模板中的规则集编码必须已存在。", "", "", "", "", ""],
  ["2", "填写或粘贴规则", "在“规则填写模板”第 6 行开始填写，一行一条规则；多值字段统一使用中文分号“；”分隔。", "", "", "", "", ""],
  ["3", "检查填写状态", "查看右侧“填写检查”和“问题提示”。状态为“通过”后再交付或导入。", "", "", "", "", ""],
  ["4", "抽样试审", "批量导入后，应对高风险规则和典型规则使用平台“试审规则”功能验证，避免仅凭文字描述上线。", "", "", "", "", ""],
];
guide.mergeCells("B5:H5");
guide.mergeCells("B6:B6");
guide.mergeCells("C6:H6");
guide.mergeCells("C7:H7");
guide.mergeCells("C8:H8");
guide.mergeCells("C9:H9");
body(guide.getRange("A5:H9"));
guide.getRange("A5:C5").format = {
  fill: colors.sky,
  font: { bold: true, color: colors.navy },
  borders: { preset: "all", color: colors.border, style: "thin" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};

section(guide, "A11:H11", "质量底线");
guide.getRange("A12:H18").values = [
  ["检查项", "要求", "", "", "", "", "", ""],
  ["可判定", "检查逻辑必须写清检查对象、通过条件和不通过条件，避免“应合理”“建议完整”等无法稳定判定的表述。", "", "", "", "", "", ""],
  ["可定位", "规则应明确作用范围；只检查某些章节时填写目标章节关键词，只检查具体要素时填写必需要素。", "", "", "", "", "", ""],
  ["可追溯", "有标准依据时填写标准/制度名称及条款号；内部要求可填写文件名称、版本和条款摘要。", "", "", "", "", "", ""],
  ["不重复", "规则编号全局唯一且保持稳定；规则名称和检查逻辑不得与已有规则重复或实质冲突。", "", "", "", "", "", ""],
  ["可验证", "导入后至少准备一段应通过样例和一段应失败样例进行试审。样例文本不作为导入字段。", "", "", "", "", "", ""],
  ["引擎适配", "当前规则引擎只支持“表格字段格式检查”。其他语义、完整性、一致性要求优先选择 LLM。", "", "", "", "", "", ""],
];
for (let r = 12; r <= 18; r++) guide.mergeCells(`B${r}:H${r}`);
body(guide.getRange("A12:H18"));
guide.getRange("A12:B12").format = {
  fill: colors.sky,
  font: { bold: true, color: colors.navy },
  borders: { preset: "all", color: colors.border, style: "thin" },
  horizontalAlignment: "center",
};
guide.getRange("A20:H21").merge();
guide.getRange("A20:H21").values = [[
  "注意：本工作簿用于先统一规则整理口径，并为后续批量导入功能提供固定模板。当前平台内部字段 rule_id、category、phase、aliases、pattern 由系统生成或使用默认值，不要求人工填写。"
]];
guide.getRange("A20:H21").format = {
  fill: colors.paleOrange,
  font: { bold: true, color: "#7F4125" },
  wrapText: true,
  verticalAlignment: "center",
  borders: { preset: "all", color: colors.orange, style: "thin" },
};
guide.getRange("A:A").format.columnWidthPx = 95;
guide.getRange("B:B").format.columnWidthPx = 130;
guide.getRange("C:H").format.columnWidthPx = 110;
guide.getRange("5:21").format.rowHeightPx = 36;
guide.freezePanes.freezeRows(4);

// 规则填写模板
title(
  rules,
  "A1:T1",
  "规则填写模板",
  "一行一条规则。红色 * 为必填；橙色为条件必填；灰色列由 Excel 自动检查，请勿填写。可直接复制空白行扩充。"
);
rules.showGridLines = false;
rules.getRange("A4:T4").merge();
rules.getRange("A4:T4").values = [[
  "审查方式说明：LLM = 自然语言语义审查；规则引擎 = 确定性表格字段格式检查；规则+LLM = 两者同时执行。当前前端仅展示 LLM/规则引擎，但后端已支持规则+LLM。"
]];
rules.getRange("A4:T4").format = {
  fill: colors.paleGreen,
  font: { color: "#385723", bold: true },
  wrapText: true,
  borders: { preset: "all", color: colors.border, style: "thin" },
};
const ruleHeaders = [
  "序号",
  "规则集编码 *",
  "规则编号 *",
  "规则名称 *",
  "规则描述",
  "检查逻辑 *",
  "审查方式 *",
  "严重程度 *",
  "是否启用 *",
  "检查范围 *",
  "目标章节关键词",
  "必需要素",
  "标准依据",
  "检查类型\n（条件必填）",
  "字段名称\n（条件必填）",
  "匹配方式\n（条件必填）",
  "匹配内容\n（条件必填）",
  "备注",
  "填写检查\n（系统）",
  "问题提示\n（系统）",
];
rules.getRange("A5:T5").values = [ruleHeaders];
header(rules.getRange("A5:M5"));
header(rules.getRange("N5:Q5"), "#C65911");
header(rules.getRange("R5:R5"), colors.blue);
header(rules.getRange("S5:T5"), "#7F8C8D");

const blankRows = 100;
rules.getRange(`A6:T${5 + blankRows}`).values = Array.from({ length: blankRows }, (_, i) => [
  i + 1, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
]);
body(rules.getRange(`A6:T${5 + blankRows}`));
rules.getRange(`A6:A${5 + blankRows}`).format.horizontalAlignment = "center";
rules.getRange(`G6:J${5 + blankRows}`).format.horizontalAlignment = "center";
rules.getRange(`S6:S${5 + blankRows}`).format.horizontalAlignment = "center";
rules.getRange(`N6:Q${5 + blankRows}`).format.fill = "#FFF2CC";
rules.getRange(`S6:T${5 + blankRows}`).format.fill = colors.paleGray;

rules.getRange("S6").formulas = [[
  '=IF(B6&C6&D6&E6&F6&G6&H6&I6&J6&K6&L6&M6&N6&O6&P6&Q6&R6="","",IF(OR(B6="",C6="",D6="",F6="",G6="",H6="",I6="",J6=""),"缺少必填项",IF(AND(OR(G6="规则引擎",G6="规则+LLM"),OR(N6="",O6="",P6="",Q6="")),"缺少规则引擎参数","通过")))'
]];
rules.getRange(`S6:S${5 + blankRows}`).fillDown();
rules.getRange("T6").formulas = [[
  '=IF(S6="","",IF(S6="通过","",IF(S6="缺少必填项","请补齐规则集编码、规则编号、规则名称、检查逻辑、审查方式、严重程度、是否启用和检查范围","规则引擎/规则+LLM需填写检查类型、字段名称、匹配方式和匹配内容")))'
]];
rules.getRange(`T6:T${5 + blankRows}`).fillDown();

rules.getRange(`G6:G${5 + blankRows}`).dataValidation = {
  rule: { type: "list", values: ["LLM", "规则引擎", "规则+LLM"] },
};
rules.getRange(`H6:H${5 + blankRows}`).dataValidation = {
  rule: { type: "list", values: ["错误", "警告", "信息"] },
};
rules.getRange(`I6:I${5 + blankRows}`).dataValidation = {
  rule: { type: "list", values: ["是", "否"] },
};
rules.getRange(`J6:J${5 + blankRows}`).dataValidation = {
  rule: { type: "list", values: ["全文", "封面", "签署页", "前言", "正文"] },
};
rules.getRange(`N6:N${5 + blankRows}`).dataValidation = {
  rule: { type: "list", values: ["", "表格字段格式检查"] },
};
rules.getRange(`P6:P${5 + blankRows}`).dataValidation = {
  rule: { type: "list", values: ["", "开头是", "结尾是", "包含", "完全等于"] },
};

rules.getRange(`S6:S${5 + blankRows}`).conditionalFormats.add("containsText", {
  text: "通过",
  format: { fill: colors.paleGreen, font: { color: "#385723", bold: true } },
});
rules.getRange(`S6:S${5 + blankRows}`).conditionalFormats.add("containsText", {
  text: "缺少",
  format: { fill: colors.paleRed, font: { color: colors.red, bold: true } },
});
rules.freezePanes.freezeRows(5);
rules.freezePanes.freezeColumns(4);

const ruleWidths = [55, 110, 95, 150, 190, 300, 100, 90, 85, 90, 160, 170, 210, 130, 160, 105, 130, 150, 125, 280];
ruleWidths.forEach((w, i) => rules.getRangeByIndexes(0, i, 105, 1).format.columnWidthPx = w);
rules.getRange(`6:${5 + blankRows}`).format.rowHeightPx = 42;

// 规则集定义
title(
  sets,
  "A1:F1",
  "规则集定义",
  "规则必须归属于一个规则集。先在平台创建规则集，或在未来批量导入时先导入本页，再导入“规则填写模板”。"
);
sets.showGridLines = false;
sets.getRange("A5:F5").values = [[
  "规则集编码 *",
  "规则集名称 *",
  "规则集说明",
  "是否新建 *",
  "质量要求",
  "备注",
]];
header(sets.getRange("A5:F5"));
sets.getRange("A6:F15").values = [
  ["product_requirement", "产品需求文档规则", "用于产品需求类文档的内容、完整性与一致性审查", "是", "编码仅使用英文字母、数字和下划线；名称应体现适用文档或业务范围", ""],
  ["test_outline", "试验大纲规则", "用于试验大纲的章节、试验项目与依据审查", "是", "同一规则集内规则应服务于相近文档类型，避免成为无边界的规则集合", ""],
  ...Array.from({ length: 8 }, () => ["", "", "", "", "", ""]),
];
body(sets.getRange("A6:F15"));
sets.getRange("D6:D15").dataValidation = { rule: { type: "list", values: ["是", "否"] } };
sets.freezePanes.freezeRows(5);
[150, 180, 290, 100, 330, 180].forEach((w, i) => sets.getRangeByIndexes(0, i, 15, 1).format.columnWidthPx = w);
sets.getRange("6:15").format.rowHeightPx = 45;

// 字段说明
title(
  fields,
  "A1:J1",
  "字段说明与导入映射",
  "“平台字段”列用于后续开发批量导入接口；普通填写人员主要关注必填性、填写要求和示例。"
);
fields.showGridLines = false;
const fieldHeaders = ["Excel 列名", "平台字段", "必填性", "适用条件", "允许值/格式", "填写要求", "正例", "常见问题", "系统处理", "是否出现在前端"];
fields.getRange("A5:J5").values = [fieldHeaders];
header(fields.getRange("A5:J5"));
const fieldRows = [
  ["规则集编码", "source", "必填", "全部", "已存在的规则集编码", "必须与规则集定义一致；建议英文、数字、下划线组合", "test_outline", "填写规则集显示名称导致无法匹配", "按编码关联规则集", "所属规则集由当前页面选择"],
  ["规则编号", "code", "必填", "全部", "全局唯一文本；建议 XX-001", "编号一经启用尽量不改，用于追踪规则版本和问题来源", "P-006", "与已有规则重复；使用无规律临时编号", "生成 aliases；参与内部 rule_id 生成", "是"],
  ["规则名称", "name", "必填", "全部", "建议 8-30 字", "用“检查对象 + 检查要求”命名，单条规则只表达一个核心检查点", "阶段标识格式检查", "名称过泛，如“格式检查”；一条规则混入多个无关要求", "生成 aliases；参与内部 rule_id 生成", "是"],
  ["规则描述", "description", "选填但建议", "全部", "简洁文本", "说明规则目的、风险或适用场景，不重复照抄检查逻辑", "确保封面阶段标识符合项目命名规范", "只写“请检查”或与逻辑完全重复", "原样保存", "是"],
  ["检查逻辑", "logic", "必填", "全部", "自然语言", "必须包含检查对象、通过条件、不通过条件；必要时写例外条件", "检查封面表格中的阶段标识；字段值以“-AB”结尾时通过，否则报告实际值和期望格式", "只有标准原文，没有判定方式；使用“合理、适当”等模糊词", "作为 LLM 提示或规则说明", "是"],
  ["审查方式", "review_type", "必填", "全部", "LLM/规则引擎/规则+LLM", "语义、完整性、一致性优先 LLM；确定性字段格式可用规则引擎", "规则引擎", "规则能力不支持却选择规则引擎", "映射 llm/rule/both", "是；当前新建页展示 LLM、规则引擎"],
  ["严重程度", "severity", "必填", "全部", "错误/警告/信息", "错误=不满足关键要求；警告=需人工确认；信息=提示优化", "警告", "所有规则均设置为错误，导致报告失去优先级", "映射 error/warning/info", "是"],
  ["是否启用", "enabled", "必填", "全部", "是/否", "未完成验证的规则先设为否；试审通过后再启用", "是", "规则尚未验证即批量启用", "映射 true/false", "创建时默认启用，前端未单独填写"],
  ["检查范围", "scope", "必填", "全部", "全文/封面/签署页/前言/正文", "选择能覆盖目标且最小的范围，减少误报和无关 LLM 输入", "正文", "全部选择全文，导致定位差和成本增加", "映射 all/cover/signature/preface/body", "是"],
  ["目标章节关键词", "target_headings", "选填", "限定章节时", "多值用中文分号；分隔", "填写稳定、可识别的章节标题关键词；不要堆砌近义词", "接口要求；机械接口；电气接口", "填写完整长句；关键词过泛", "拆分为字符串数组", "是"],
  ["必需要素", "required_elements", "选填", "检查章节完整性时", "多值用中文分号；分隔", "填写可在文档中定位的名词或短语，表示该章节应覆盖的内容", "机械接口；电气接口；电源接口", "填写抽象要求，如“内容合理”", "拆分为字符串数组", "是"],
  ["标准依据", "standard_ref", "选填但建议", "有依据时", "标准/文件名 + 条款号或摘要", "优先填写可追溯条款；不能公开原文时写内部文件名称、版本、条款号和可维护摘要", "GJB XXXX-XXXX 第 5.2 条", "只写“按国军标”；粘贴大段受控原文", "原样保存并展示为依据", "是"],
  ["检查类型", "params.check_type", "条件必填", "规则引擎/规则+LLM", "表格字段格式检查", "当前平台规则引擎仅支持这一类型", "表格字段格式检查", "填写未实现的自定义检查类型", "映射 table_field_regex", "规则引擎区固定显示"],
  ["字段名称", "params.field_labels", "条件必填", "规则引擎/规则+LLM", "多值用中文分号；分隔", "填写表格中可能出现的字段标签或同义标签", "阶段标识；审查阶段标识", "填写字段值而非字段标签", "拆分为字符串数组", "是"],
  ["匹配方式", "params.match_mode", "条件必填", "规则引擎/规则+LLM", "开头是/结尾是/包含/完全等于", "选择字段值与匹配内容之间的关系", "结尾是", "把完整正则表达式填入本列", "映射 starts_with/ends_with/contains/equals", "是"],
  ["匹配内容", "params.match_value", "条件必填", "规则引擎/规则+LLM", "文本", "只填写需要匹配的固定文本，不填写正则语法", "-AB", "遗漏符号；自行填写转义字符", "后端自动转义并生成 pattern", "是"],
  ["序号", "-", "选填", "全部", "正整数", "仅用于 Excel 阅读和沟通，不作为规则唯一标识", "1", "把序号当成规则编号", "导入时忽略", "否"],
  ["备注", "-", "选填", "全部", "文本", "记录待确认事项、责任人或来源，不进入审查逻辑", "待质量部门确认条款号", "把关键判定条件只写在备注", "导入时忽略", "否"],
];
fields.getRange(`A6:J${5 + fieldRows.length}`).values = fieldRows;
body(fields.getRange(`A6:J${5 + fieldRows.length}`));
fields.getRange(`C6:C${5 + fieldRows.length}`).format.horizontalAlignment = "center";
fields.getRange(`C6:C${5 + fieldRows.length}`).conditionalFormats.add("containsText", {
  text: "必填",
  format: { fill: colors.paleOrange, font: { color: "#9C0006", bold: true } },
});
fields.freezePanes.freezeRows(5);
[150, 135, 100, 145, 175, 310, 210, 260, 220, 170].forEach((w, i) => fields.getRangeByIndexes(0, i, 5 + fieldRows.length, 1).format.columnWidthPx = w);
fields.getRange(`6:${5 + fieldRows.length}`).format.rowHeightPx = 62;

// 填写示例
title(
  examples,
  "A1:T1",
  "填写示例",
  "示例覆盖 LLM、规则引擎、规则+LLM 三种方式。实际使用时复制结构，不要机械复制示例内容。"
);
examples.showGridLines = false;
examples.getRange("A5:T5").values = [ruleHeaders];
header(examples.getRange("A5:M5"));
header(examples.getRange("N5:Q5"), "#C65911");
header(examples.getRange("R5:R5"), colors.blue);
header(examples.getRange("S5:T5"), "#7F8C8D");
examples.getRange("A6:T8").values = [
  [1, "test_outline", "T-001", "试验项目范围完整性检查", "检查试验大纲是否明确覆盖规定的自然环境试验项目", "定位“范围”或“试验项目”章节。正文应明确包含温度、高度、温度变化、湿热等自然环境类鉴定试验；全部包含时通过，缺少任一项时指出缺失项；不得推断未提供的试验数据和判据。", "LLM", "错误", "是", "正文", "范围；试验项目", "温度；高度；温度变化；湿热", "项目试验要求第 3.1 条", "", "", "", "", "高风险完整性规则，导入后需正反样例试审", "通过", ""],
  [2, "product_requirement", "P-006", "阶段标识格式检查", "检查封面表格中的阶段标识后缀", "检查封面表格中字段名称为“阶段标识”或“审查阶段标识”的字段值；值以“-AB”结尾时通过，否则报告实际值并提示期望格式。", "规则引擎", "警告", "是", "封面", "", "", "项目文档编码规则第 4.2 条", "表格字段格式检查", "阶段标识；审查阶段标识", "结尾是", "-AB", "确定性格式规则", "通过", ""],
  [3, "product_requirement", "P-010", "接口章节覆盖与字段格式检查", "同时检查接口章节内容完整性和接口编号前缀", "在“接口要求”相关章节检查是否覆盖机械接口、电气接口、电源接口和信号接口；同时检查接口清单表中的“接口编号”字段值是否以“IF-”开头。缺少要素或格式不符时分别报告。", "规则+LLM", "警告", "否", "正文", "接口要求；机械接口；电气接口", "机械接口；电气接口；电源接口；信号接口", "接口设计规范第 5 条", "表格字段格式检查", "接口编号", "开头是", "IF-", "后端支持，当前新建页需后续补充该选项；验证完成前暂不启用", "通过", ""],
];
body(examples.getRange("A6:T8"));
examples.getRange("N6:Q8").format.fill = "#FFF2CC";
examples.getRange("S6:T8").format.fill = colors.paleGray;
examples.freezePanes.freezeRows(5);
examples.freezePanes.freezeColumns(4);
ruleWidths.forEach((w, i) => examples.getRangeByIndexes(0, i, 8, 1).format.columnWidthPx = w);
examples.getRange("6:8").format.rowHeightPx = 100;

// 枚举与规范
title(
  enums,
  "A1:H1",
  "枚举值、映射与规则质量规范",
  "Excel 使用中文值便于填写，导入程序应按本页映射为平台内部值。"
);
enums.showGridLines = false;
section(enums, "A4:D4", "枚举映射");
enums.getRange("A5:D5").values = [["字段", "Excel 填写值", "平台内部值", "使用说明"]];
header(enums.getRange("A5:D5"));
const enumRows = [
  ["审查方式", "LLM", "llm", "适合语义、完整性、一致性、标准符合性等自然语言判定"],
  ["审查方式", "规则引擎", "rule", "当前仅支持表格字段格式匹配"],
  ["审查方式", "规则+LLM", "both", "后端已支持；当前前端新建规则单选项尚未展示"],
  ["严重程度", "错误", "error", "关键要求不满足，通常必须整改"],
  ["严重程度", "警告", "warning", "存在风险或需要人工确认"],
  ["严重程度", "信息", "info", "提示优化，不影响通过"],
  ["检查范围", "全文", "all", "确实需要跨章节判断时使用"],
  ["检查范围", "封面", "cover", "封面字段、编号、名称等"],
  ["检查范围", "签署页", "signature", "签署、审批、日期等"],
  ["检查范围", "前言", "preface", "前言、编制说明等"],
  ["检查范围", "正文", "body", "正文内容和章节"],
  ["匹配方式", "开头是", "starts_with", "字段值以指定文本开头"],
  ["匹配方式", "结尾是", "ends_with", "字段值以指定文本结尾"],
  ["匹配方式", "包含", "contains", "字段值包含指定文本"],
  ["匹配方式", "完全等于", "equals", "字段值与指定文本完全一致"],
];
enums.getRange(`A6:D${5 + enumRows.length}`).values = enumRows;
body(enums.getRange(`A6:D${5 + enumRows.length}`));

section(enums, "F4:H4", "推荐的检查逻辑写法");
enums.getRange("F5:H5").values = [["组成部分", "应写内容", "示例"]];
header(enums.getRange("F5:H5"), colors.green);
const logicRows = [
  ["1. 检查对象", "检查哪个页面、章节、表格、字段或内容", "封面表格中的阶段标识字段"],
  ["2. 通过条件", "满足什么条件视为通过", "字段值以“-AB”结尾时通过"],
  ["3. 不通过条件", "什么情况报告问题", "字段缺失或值不以“-AB”结尾时不通过"],
  ["4. 输出要求", "发现问题后应指出什么", "报告实际值、期望格式和所在位置"],
  ["5. 例外/边界", "哪些情况不检查或不得推断", "字段不存在时报告缺失；不得自行补造编号"],
];
enums.getRange("F6:H10").values = logicRows;
body(enums.getRange("F6:H10"));

section(enums, "F12:H12", "导入前质量检查清单");
enums.getRange("F13:H13").values = [["序号", "检查内容", "合格标准"]];
header(enums.getRange("F13:H13"), colors.green);
const qualityRows = [
  ["1", "编号唯一性", "规则编号未与平台已有规则或本批次其他规则重复"],
  ["2", "逻辑可判定", "能明确区分通过和不通过，不依赖模糊主观词"],
  ["3", "规则原子性", "一条规则聚焦一个核心检查点；复合规则有明确分项输出"],
  ["4", "范围准确", "检查范围和目标章节足以定位，且不过度扩大"],
  ["5", "依据可追溯", "标准、制度或内部要求能定位到文件和条款"],
  ["6", "严重度合理", "严重度与实际风险匹配，不滥用“错误”"],
  ["7", "引擎可实现", "规则引擎类型在当前能力范围内，否则使用 LLM"],
  ["8", "样例已验证", "至少一条通过样例和一条失败样例试审符合预期"],
];
enums.getRange("F14:H21").values = qualityRows;
body(enums.getRange("F14:H21"));
enums.freezePanes.freezeRows(5);
[130, 130, 120, 290, 30, 130, 260, 310].forEach((w, i) => enums.getRangeByIndexes(0, i, 24, 1).format.columnWidthPx = w);
enums.getRange("6:21").format.rowHeightPx = 48;

// Add structured tables after values/formulas are in place.
const rulesTable = rules.tables.add(`A5:T${5 + blankRows}`, true, "RuleInputTable");
rulesTable.style = "TableStyleMedium2";
rulesTable.showBandedRows = true;
const setTable = sets.tables.add("A5:F15", true, "RuleSetTable");
setTable.style = "TableStyleMedium4";
const fieldTable = fields.tables.add(`A5:J${5 + fieldRows.length}`, true, "RuleFieldTable");
fieldTable.style = "TableStyleMedium2";
const exampleTable = examples.tables.add("A5:T8", true, "RuleExampleTable");
exampleTable.style = "TableStyleMedium2";

await fs.mkdir(previewDir, { recursive: true });
for (const [sheetName, range] of [
  ["填写说明", "A1:H21"],
  ["规则填写模板", "A1:T16"],
  ["规则集定义", "A1:F15"],
  ["字段说明", `A1:J${5 + fieldRows.length}`],
  ["填写示例", "A1:T8"],
  ["枚举与规范", "A1:H21"],
]) {
  const rendered = await wb.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await rendered.arrayBuffer()));
}

const inspection = await wb.inspect({
  kind: "table",
  range: "规则填写模板!A1:T10",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 20,
  maxChars: 8000,
});
await fs.writeFile(path.join(outputDir, "inspection.ndjson"), inspection.ndjson, "utf8");

const errors = await wb.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
await fs.writeFile(path.join(outputDir, "formula-errors.ndjson"), errors.ndjson, "utf8");

await fs.mkdir(outputDir, { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(outputPath);
console.log(outputPath);
