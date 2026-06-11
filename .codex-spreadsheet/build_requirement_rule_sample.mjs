import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = path.resolve("../web/static/files/审查规则导入模板.xlsx");
const outputDir = path.resolve("../outputs/rule-import-template");
const outputPath = path.join(outputDir, "需求文档规则集-5条测试规则.xlsx");
const previewPath = path.join(outputDir, "需求文档规则集-5条测试规则.png");

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItem("规则导入");

const rows = [
  [
    1,
    "RD-101",
    "功能需求完整性检查",
    "定位“功能需求”“功能要求”或同类章节。每项主要功能需求应明确描述触发条件、处理过程或功能行为以及预期输出；三项内容均明确时通过。若仅描述功能名称、缺少输入条件、处理逻辑或输出结果，应指出具体缺失内容和所在章节，不得自行补造需求。",
    "检查主要功能需求是否形成可理解、可实现的完整描述。",
    "LLM",
    "错误",
    "正文",
    "功能需求；功能要求；功能描述",
    "触发条件；功能行为；预期输出",
    "",
    "",
    "",
    "",
    "",
  ],
  [
    2,
    "RD-102",
    "技术指标可验证性检查",
    "检查性能指标、技术指标及约束条件。指标应尽量包含明确的对象、量值或范围、单位以及适用条件，并能够通过试验、分析、检查或演示等方式验证。指标完整且可判定时通过；存在“性能良好”“响应迅速”“满足使用要求”等模糊表述，或缺少必要量值、单位、边界条件时，应指出原文及缺失项。模板明确要求待定的内容可标记为“待补充”，不得推断数值。",
    "检查需求是否量化、可判定并具备后续验证条件。",
    "LLM",
    "错误",
    "正文",
    "性能要求；技术指标；环境要求；可靠性要求",
    "指标对象；量值或范围；单位；适用条件；验证方式",
    "",
    "",
    "",
    "",
    "",
  ],
  [
    3,
    "RD-103",
    "接口需求覆盖性检查",
    "定位“接口要求”“接口需求”或同类章节。应根据产品实际边界说明机械接口、电气接口、电源接口和通信或信号接口；不适用的接口类型应明确说明不适用。对于已涉及的接口，应描述接口对象、连接关系以及关键参数或约束。覆盖完整时通过；接口类型遗漏、仅列名称而无约束，或正文前后描述冲突时，应逐项指出。",
    "检查产品外部接口类型及关键约束是否完整。",
    "LLM",
    "警告",
    "正文",
    "接口要求；接口需求；外部接口",
    "机械接口；电气接口；电源接口；通信或信号接口",
    "",
    "",
    "",
    "",
    "",
  ],
  [
    4,
    "RD-104",
    "需求表述唯一性检查",
    "检查需求条目是否存在歧义、多个要求混写或不可判定的选择性表述。单条需求应表达一个主要约束，责任对象和动作明确；程度性、选择性或兜底性措辞必须给出适用条件和判定边界。表述唯一且可形成明确结论时通过；发现复合需求、未定义措辞或歧义时，应引用问题原文并建议拆分或补充边界条件，但不得改变原需求意图。",
    "检查单条需求是否清晰、原子化并避免歧义。",
    "LLM",
    "警告",
    "正文",
    "需求；要求；功能需求；性能要求",
    "",
    "",
    "",
    "",
    "",
    "",
  ],
  [
    5,
    "RD-105",
    "需求一致性与冲突检查",
    "跨章节检查相同对象的名称、状态、指标数值、单位、工作模式和接口约束是否一致。相同概念采用统一名称，重复出现的指标与约束无矛盾时通过。若同一参数出现不同数值或单位、同一功能在不同章节的适用条件冲突、简称与全称无法对应，或需求与引用文件摘要明显矛盾，应列出冲突位置和两处原文；无法判断哪一处正确时提示人工确认，不得擅自选择。",
    "检查需求文档内部以及需求与引用依据之间的一致性。",
    "LLM",
    "错误",
    "正文",
    "",
    "名称；指标数值；单位；工作模式；接口约束",
    "",
    "",
    "",
    "",
    "",
  ],
];

sheet.getRange("A6:O10").values = rows;
sheet.getRange("A6:O10").format.wrapText = true;
sheet.getRange("6:10").format.rowHeightPx = 96;

await fs.mkdir(outputDir, { recursive: true });
const preview = await workbook.render({
  sheetName: "规则导入",
  range: "A1:P10",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const inspection = await workbook.inspect({
  kind: "table",
  range: "规则导入!A5:P10",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 16,
  maxChars: 8000,
});
await fs.writeFile(path.join(outputDir, "需求文档规则集-5条测试规则-inspection.ndjson"), inspection.ndjson, "utf8");

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula error scan",
});
await fs.writeFile(path.join(outputDir, "需求文档规则集-5条测试规则-errors.ndjson"), errors.ndjson, "utf8");

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
