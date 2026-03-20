from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from core.executor import DocumentReviewResult, SectionReviewResult
from rules.base_rule import RuleSeverity


class BaseReporter(ABC):
    @abstractmethod
    def generate(self, result: DocumentReviewResult) -> str:
        pass
    
    @abstractmethod
    def save(self, result: DocumentReviewResult, output_path: str):
        pass

class MarkdownReporter(BaseReporter):
    def generate(self, result: DocumentReviewResult) -> str:
        lines = []
        
        lines.append("# 文档审查报告")
        lines.append("")
        
        lines.append("## 基本信息")
        lines.append("")
        lines.append(f"- **文档标题**: {result.document_title}")
        lines.append(f"- **文档路径**: `{result.document_path}`")
        lines.append(f"- **审查时间**: {result.review_time}")
        status_emoji = "✅" if result.overall_passed else "❌"
        lines.append(f"- **审查结果**: {status_emoji} {'通过' if result.overall_passed else '未通过'}")
        lines.append("")
        
        lines.append("## 审查统计")
        lines.append("")
        lines.append("| 指标 | 数量 |")
        lines.append("|------|------|")
        lines.append(f"| 总问题数 | {result.total_issues} |")
        lines.append(f"| 错误 | {result.errors} |")
        lines.append(f"| 警告 | {result.warnings} |")
        if hasattr(result, 'llm_issues') and result.llm_issues > 0:
            lines.append(f"| LLM问题 | {result.llm_issues} |")
        lines.append("")
        
        if result.summary:
            lines.append("## 审查总结")
            lines.append("")
            lines.append(result.summary)
            lines.append("")
        
        lines.append("## 详细结果")
        lines.append("")
        
        for section_result in result.section_results:
            if not section_result.passed:
                lines.append(f"### 章节 {section_result.section_id}")
                lines.append("")
                lines.append(f"> {section_result.section_text[:100]}...")
                lines.append("")
                
                lines.append("| 规则 | 严重程度 | 描述 | 建议 |")
                lines.append("|------|----------|------|------|")
                
                for rule_result in section_result.rule_results:
                    if not rule_result.passed:
                        severity_str = {
                            RuleSeverity.ERROR: "🔴 错误",
                            RuleSeverity.WARNING: "🟡 警告",
                            RuleSeverity.INFO: "🔵 信息"
                        }.get(rule_result.severity, "未知")
                        
                        suggestions = "; ".join(rule_result.suggestions) if rule_result.suggestions else "-"
                        lines.append(f"| {rule_result.rule_name} | {severity_str} | {rule_result.message} | {suggestions} |")
                
                lines.append("")

                if section_result.llm_review:
                    lines.append("#### 🤖 LLM审查结果")
                    if section_result.llm_review.get("summary"):
                        lines.append(f"**总结**: {section_result.llm_review.get('summary')}")
                        lines.append("")
                    for issue in section_result.llm_review.get("issues", []):
                        lines.append(f"- **{issue.get('severity')}**: {issue.get('description')}")
                        lines.append(f"  - 建议: {issue.get('suggestion')}")
                    lines.append("")


        lines.append("---")
        lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return "\n".join(lines)
    
    def save(self, result: DocumentReviewResult, output_path: str):
        content = self.generate(result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)


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
                "warnings": result.warnings,
                "llm_issues": getattr(result, 'llm_issues', 0)
            },
            "summary": result.summary,
            "issues": []
        }

        # 规则问题
        for section_result in result.section_results:
            for rule_result in section_result.rule_results:
                if not rule_result.passed:
                    data["issues"].append({
                        "source": "rule",
                        "section_id": section_result.section_id,
                        "content": section_result.section_text[:100] + "...",
                        "severity": rule_result.severity.name,
                        "message": rule_result.message,
                        "suggestions": rule_result.suggestions or []
                    })

        # LLM问题
        for section_result in result.section_results:
            if section_result.llm_review:
                for issue in section_result.llm_review.get("issues", []):
                    data["issues"].append({
                        "source": "llm",
                        "section_id": section_result.section_id,
                        "content": section_result.section_text[:100] + "...",
                        "severity": issue.get("severity", "info"),
                        "message": issue.get("description", ""),
                        "suggestions": [issue.get("suggestion", "")] if issue.get("suggestion") else []
                    })

        # 如果有整体 LLM 总结，也可附加
        if getattr(result, 'llm_summary', None):
            data["llm_summary"] = result.llm_summary

        return json.dumps(data, ensure_ascii=False, indent=2)

    def save(self, result: DocumentReviewResult, output_path: str):
        content = self.generate(result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)


class DocxReporter(BaseReporter):
    def generate(self, result: DocumentReviewResult) -> Document:
        doc = Document()

        # ----------------------------
        # 标题
        # ----------------------------
        title = doc.add_heading('文档审查报告', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # ----------------------------
        # 基本信息
        # ----------------------------
        doc.add_heading('基本信息', level=1)
        info_table = doc.add_table(rows=4, cols=2)
        info_table.style = 'Table Grid'
        info_table.cell(0, 0).text = '文档标题'
        info_table.cell(0, 1).text = result.document_title
        info_table.cell(1, 0).text = '文档路径'
        info_table.cell(1, 1).text = result.document_path
        info_table.cell(2, 0).text = '审查时间'
        info_table.cell(2, 1).text = result.review_time
        info_table.cell(3, 0).text = '审查结果'
        info_table.cell(3, 1).text = '通过' if result.overall_passed else '未通过'

        # ----------------------------
        # 审查统计
        # ----------------------------
        doc.add_heading('审查统计', level=1)
        stats_table = doc.add_table(rows=4, cols=2)
        stats_table.style = 'Table Grid'
        stats_table.cell(0, 0).text = '总问题数'
        stats_table.cell(0, 1).text = str(result.total_issues)
        stats_table.cell(1, 0).text = '错误数'
        stats_table.cell(1, 1).text = str(result.errors)
        stats_table.cell(2, 0).text = '警告数'
        stats_table.cell(2, 1).text = str(result.warnings)
        stats_table.cell(3, 0).text = 'LLM问题数'
        stats_table.cell(3, 1).text = str(getattr(result, 'llm_issues', 0))

        # ----------------------------
        # 规则审查问题
        # ----------------------------
        doc.add_heading('规则审查问题', level=1)
        rule_table = doc.add_table(rows=1, cols=4)
        rule_table.style = 'Table Grid'
        hdr_cells = rule_table.rows[0].cells
        hdr_cells[0].text = '内容片段'
        hdr_cells[1].text = '问题类型'
        hdr_cells[2].text = '问题描述'
        hdr_cells[3].text = '建议'

        for section_result in result.section_results:
            for rule_result in section_result.rule_results:
                if not rule_result.passed:
                    row_cells = rule_table.add_row().cells
                    row_cells[0].text = section_result.section_text[:100] + '...'
                    row_cells[1].text = rule_result.severity.name
                    row_cells[2].text = rule_result.message
                    row_cells[3].text = '; '.join(rule_result.suggestions) if rule_result.suggestions else '-'

        # ----------------------------
        # LLM审查问题
        # ----------------------------
        doc.add_heading('LLM审查问题', level=1)
        llm_table = doc.add_table(rows=1, cols=4)
        llm_table.style = 'Table Grid'
        hdr_cells = llm_table.rows[0].cells
        hdr_cells[0].text = '内容片段'
        hdr_cells[1].text = '严重程度'
        hdr_cells[2].text = '问题描述'
        hdr_cells[3].text = '建议'

        for section_result in result.section_results:
            if section_result.llm_review:
                for issue in section_result.llm_review.get('issues', []):
                    row_cells = llm_table.add_row().cells
                    row_cells[0].text = section_result.section_text[:100] + '...'
                    row_cells[1].text = issue.get('severity', 'info')
                    row_cells[2].text = issue.get('description', '')
                    row_cells[3].text = issue.get('suggestion', '')

        # ----------------------------
        # 审查总结
        # ----------------------------
        if result.summary:
            doc.add_heading('审查总结', level=1)
            doc.add_paragraph(result.summary)

        # ----------------------------
        # 页脚
        # ----------------------------
        for section in doc.sections:
            footer = section.footer
            footer.add_paragraph(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return doc

    def save(self, result: DocumentReviewResult, output_path: str):
        doc = self.generate(result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)


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