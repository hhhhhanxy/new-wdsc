from abc import ABC, abstractmethod
from typing import List, Optional
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches
from web.time_utils import beijing_now_str

from core.executor import DocumentReviewResult, SectionReviewResult
from rules.base_rule import RuleSeverity


class BaseReporter(ABC):
    @abstractmethod
    def generate(self, result: DocumentReviewResult) -> str:
        pass
    
    @abstractmethod
    def save(self, result: DocumentReviewResult, output_path: str):
        pass


# ----------------------------
# Markdown 报告
# ----------------------------
class MarkdownReporter(BaseReporter):
    def generate(self, result: DocumentReviewResult) -> str:
        lines = []
        
        lines.append("# 文档审查报告\n")
        
        # 基本信息
        lines.append("## 基本信息\n")
        lines.append(f"- **文档标题**: {result.document_title}")
        lines.append(f"- **文档路径**: `{result.document_path}`")
        lines.append(f"- **审查时间**: {result.review_time}")
        status_emoji = "✅" if result.overall_passed else "❌"
        lines.append(f"- **审查结果**: {status_emoji} {'通过' if result.overall_passed else '未通过'}\n")
        
        # 审查统计
        lines.append("## 审查统计\n")
        lines.append("| 指标 | 数量 |")
        lines.append("|------|------|")
        lines.append(f"| 总问题数 | {result.total_issues} |")
        lines.append(f"| 错误 | {result.errors} |")
        lines.append(f"| 警告 | {result.warnings} |\n")
        
        # 审查总结
        if result.summary:
            lines.append("## 审查总结\n")
            lines.append(result.summary + "\n")
        
        # 章节及问题
        lines.append("## 详细结果\n")
        for section in result.section_results:
            lines.append(f"### 章节 {section.section_id}\n")
            lines.append(f"> {section.section_text[:200]}...\n")
            
            # 规则问题
            if any(not r.passed for r in section.rule_results):
                lines.append("#### 规则问题\n")
                lines.append("| 规则 | 来源 | 严重程度 | 复核状态 | 描述 | 建议 |")
                lines.append("|------|------|----------|----------|------|------|")
                for r in section.rule_results:
                    if not r.passed:
                        severity_str = {
                            RuleSeverity.ERROR: "🔴 错误",
                            RuleSeverity.WARNING: "🟡 警告",
                            RuleSeverity.INFO: "🔵 信息"
                        }.get(r.severity, "未知")
                        suggestions = "; ".join(r.suggestions) if r.suggestions else "-"
                        review_status = r.details.get("review_status_label", "待复核")
                        lines.append(f"| {r.rule_name} | {r.rule_source} | {severity_str} | {review_status} | {r.message} | {suggestions} |")
                lines.append("")
            


        lines.append("---")
        lines.append(f"*报告生成时间: {beijing_now_str()}*")
        return "\n".join(lines)

    def save(self, result: DocumentReviewResult, output_path: str):
        content = self.generate(result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)


# ----------------------------
# JSON 报告
# ----------------------------
class JsonReporter(BaseReporter):
    def generate(self, result: DocumentReviewResult) -> str:
        import json
        data = {
            "document_title": result.document_title,
            "document_path": result.document_path,
            "review_time": result.review_time,
            "overall_passed": result.overall_passed,
            "statistics": {
                "total_issues": result.total_issues,
                "errors": result.errors,
                "warnings": result.warnings
            },
            "summary": result.summary,
            "sections": []
        }
        
        for section in result.section_results:
            sec = {
                "section_id": section.section_id,
                "content": section.section_text,
                "passed": section.passed,
                "rule_issues": []
            }
            
            # 规则问题（包括 RULE 和 LLM 结果）
            for r in section.rule_results:
                if not r.passed:
                    sec["rule_issues"].append({
                        "rule_name": r.rule_name,
                        "rule_source": r.rule_source,
                        "severity": r.severity.name,
                        "review_status": r.details.get("review_status", "pending"),
                        "review_status_label": r.details.get("review_status_label", "待复核"),
                        "message": r.message,
                        "suggestions": r.suggestions or []
                    })
            
            data["sections"].append(sec)
        
        # 全局LLM总结
        if getattr(result, 'llm_summary', None):
            data["llm_summary"] = result.llm_summary
        
        return json.dumps(data, ensure_ascii=False, indent=2)

    def save(self, result: DocumentReviewResult, output_path: str):
        content = self.generate(result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)


# ----------------------------
# DOCX 报告
# ----------------------------
class DocxReporter(BaseReporter):
    def _severity_label(self, severity: RuleSeverity) -> str:
        return {
            RuleSeverity.ERROR: "错误",
            RuleSeverity.WARNING: "警告",
            RuleSeverity.INFO: "提示",
        }.get(severity, str(severity))

    def _source_label(self, source: str) -> str:
        return {
            "RULE": "规则引擎",
            "LLM": "LLM语义审查",
            "RULE+LLM": "规则引擎+LLM",
            "BOTH": "规则引擎+LLM",
        }.get(source or "", source or "未标明")

    def _set_table_style(self, table):
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for row in table.rows:
            for cell in row.cells:
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def _all_issues(self, result: DocumentReviewResult):
        issues = []
        for section in result.section_results:
            for rule_result in section.rule_results:
                if not rule_result.passed:
                    issues.append((section, rule_result))
        return issues

    def generate(self, result: DocumentReviewResult) -> Document:
        doc = Document()
        for section in doc.sections:
            section.top_margin = Inches(0.7)
            section.bottom_margin = Inches(0.7)
            section.left_margin = Inches(0.7)
            section.right_margin = Inches(0.7)
        
        # 标题
        title = doc.add_heading('文档审查报告', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle = doc.add_paragraph('面向用户的审查结论、问题清单与规则依据')
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        issues = self._all_issues(result)

        # 一、审查结论
        doc.add_heading('一、审查结论', level=1)
        conclusion_table = doc.add_table(rows=6, cols=2)
        self._set_table_style(conclusion_table)
        rows = [
            ('文档名称', result.document_title),
            ('文档路径', result.document_path),
            ('审查结论', '通过' if result.overall_passed else '未通过'),
            ('规则集', getattr(result, 'rule_set', 'all')),
            ('审查时间', result.review_time or getattr(result, 'completed_at', '') or '-'),
            ('报告生成时间', beijing_now_str()),
        ]
        for idx, (label, value) in enumerate(rows):
            conclusion_table.cell(idx, 0).text = label
            conclusion_table.cell(idx, 1).text = str(value or '-')
        
        doc.add_paragraph(
            f"本次审查共发现 {result.total_issues} 个问题，其中错误 {result.errors} 个、"
            f"警告 {result.warnings} 个、LLM语义审查问题 {getattr(result, 'llm_issues', 0)} 个。"
        )
        if result.summary:
            doc.add_paragraph(f"审查总结：{result.summary}")
        
        # 二、问题总览
        doc.add_heading('二、问题总览', level=1)
        if not issues:
            doc.add_paragraph('未发现不符合项。')
        else:
            overview = doc.add_table(rows=1, cols=8)
            self._set_table_style(overview)
            headers = ['序号', '位置', '规则', '审查方式', '级别', '复核状态', '问题描述', '建议']
            for idx, header in enumerate(headers):
                overview.rows[0].cells[idx].text = header
            for idx, (section, issue) in enumerate(issues, start=1):
                row = overview.add_row().cells
                row[0].text = str(idx)
                row[1].text = section.section_id or '-'
                row[2].text = issue.rule_name or issue.rule_id or '-'
                row[3].text = issue.details.get('source_label') or self._source_label(issue.rule_source)
                row[4].text = self._severity_label(issue.severity)
                row[5].text = issue.details.get('review_status_label', '待复核')
                row[6].text = issue.message or '-'
                row[7].text = '；'.join(issue.suggestions) if issue.suggestions else '-'

        # 三、本次审查规则依据与定位详情
        doc.add_heading('三、本次审查规则依据与定位详情', level=1)
        if issues:
            for idx, (section, issue) in enumerate(issues, start=1):
                rule_code = issue.details.get("rule_code") or issue.rule_id or "-"
                doc.add_heading(f"{idx}. {issue.rule_name or rule_code}", level=2)
                detail_table = doc.add_table(rows=7, cols=2)
                self._set_table_style(detail_table)
                detail_rows = [
                    ('规则编号', rule_code),
                    ('审查方式', issue.details.get('source_label') or self._source_label(issue.rule_source)),
                    ('严重级别', self._severity_label(issue.severity)),
                    ('复核状态', issue.details.get('review_status_label', '待复核')),
                    ('标准依据', issue.rule_reference or '-'),
                    ('问题描述', issue.message or '-'),
                    ('修改建议', '；'.join(issue.suggestions) if issue.suggestions else '-'),
                ]
                for row_idx, (label, value) in enumerate(detail_rows):
                    detail_table.cell(row_idx, 0).text = label
                    detail_table.cell(row_idx, 1).text = value

                if issue.details.get("rule_logic"):
                    doc.add_paragraph(f"检查逻辑：{issue.details['rule_logic']}")
                snippet = (section.section_text or '').strip()
                if snippet:
                    doc.add_paragraph(f"相关片段：{snippet[:500]}{'...' if len(snippet) > 500 else ''}")
        
        # 页脚
        for section in doc.sections:
            footer = section.footer
            footer.add_paragraph(f"报告生成时间: {beijing_now_str()}")
        
        return doc

    def save(self, result: DocumentReviewResult, output_path: str):
        doc = self.generate(result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)


# ----------------------------
# Reporter Factory
# ----------------------------
class ReporterFactory:
    _reporters = {
        "md": MarkdownReporter,
        "markdown": MarkdownReporter,
        "json": JsonReporter,
        "docx": DocxReporter,
    }

    @classmethod
    def create_reporter(cls, format_type: str) -> BaseReporter:
        reporter_class = cls._reporters.get(format_type.lower())
        if reporter_class:
            return reporter_class()
        raise ValueError(f"Unknown reporter format: {format_type}")

    @classmethod
    def register_reporter(cls, format_type: str, reporter_class: type):
        cls._reporters[format_type.lower()] = reporter_class

    @classmethod
    def get_supported_formats(cls) -> List[str]:
        return list(cls._reporters.keys())
