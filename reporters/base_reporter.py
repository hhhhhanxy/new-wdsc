from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from pathlib import Path
from docx import Document
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
        lines.append(f"| 警告 | {result.warnings} |")
        lines.append(f"| LLM问题 | {getattr(result, 'llm_issues', 0)} |\n")
        
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
                lines.append("| 规则 | 严重程度 | 描述 | 建议 |")
                lines.append("|------|----------|------|------|")
                for r in section.rule_results:
                    if not r.passed:
                        severity_str = {
                            RuleSeverity.ERROR: "🔴 错误",
                            RuleSeverity.WARNING: "🟡 警告",
                            RuleSeverity.INFO: "🔵 信息"
                        }.get(r.severity, "未知")
                        suggestions = "; ".join(r.suggestions) if r.suggestions else "-"
                        lines.append(f"| {r.rule_name} | {severity_str} | {r.message} | {suggestions} |")
                lines.append("")
            
            # LLM问题
            if section.llm_review and section.llm_review.get("issues"):
                lines.append("#### 🤖 LLM问题\n")
                for issue in section.llm_review.get("issues", []):
                    lines.append(f"- **{issue.get('severity', 'info')}**: {issue.get('description')}")
                    if issue.get('suggestion'):
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
                "warnings": result.warnings,
                "llm_issues": getattr(result, 'llm_issues', 0)
            },
            "summary": result.summary,
            "sections": []
        }
        
        for section in result.section_results:
            sec = {
                "section_id": section.section_id,
                "content": section.section_text,
                "passed": section.passed,
                "rule_issues": [],
                "llm_issues": []
            }
            
            # 规则问题
            for r in section.rule_results:
                if not r.passed:
                    sec["rule_issues"].append({
                        "rule_name": r.rule_name,
                        "severity": r.severity.name,
                        "message": r.message,
                        "suggestions": r.suggestions or []
                    })
            
            # LLM问题
            if section.llm_review and section.llm_review.get("issues"):
                for issue in section.llm_review["issues"]:
                    sec["llm_issues"].append({
                        "severity": issue.get("severity", "info"),
                        "description": issue.get("description"),
                        "suggestion": issue.get("suggestion")
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
    def generate(self, result: DocumentReviewResult) -> Document:
        doc = Document()
        
        # 标题
        title = doc.add_heading('文档审查报告', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 基本信息
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
        
        # 审查统计
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
        
        # 章节问题
        doc.add_heading('详细结果', level=1)
        for section in result.section_results:
            doc.add_heading(f"章节 {section.section_id}", level=2)
            doc.add_paragraph(section.section_text[:300] + "...")
            
            # 规则问题
            if any(not r.passed for r in section.rule_results):
                doc.add_heading("规则问题", level=3)
                tbl = doc.add_table(rows=1, cols=4)
                tbl.style = 'Table Grid'
                hdr = tbl.rows[0].cells
                hdr[0].text = "规则"
                hdr[1].text = "严重程度"
                hdr[2].text = "描述"
                hdr[3].text = "建议"
                for r in section.rule_results:
                    if not r.passed:
                        row = tbl.add_row().cells
                        row[0].text = r.rule_name
                        row[1].text = r.severity.name
                        row[2].text = r.message
                        row[3].text = "; ".join(r.suggestions) if r.suggestions else "-"
            
            # LLM问题
            if section.llm_review and section.llm_review.get("issues"):
                doc.add_heading("LLM问题", level=3)
                tbl = doc.add_table(rows=1, cols=4)
                tbl.style = 'Table Grid'
                hdr = tbl.rows[0].cells
                hdr[0].text = "内容片段"
                hdr[1].text = "严重程度"
                hdr[2].text = "描述"
                hdr[3].text = "建议"
                for issue in section.llm_review.get("issues"):
                    row = tbl.add_row().cells
                    row[0].text = section.section_text[:100] + "..."
                    row[1].text = issue.get("severity", "info")
                    row[2].text = issue.get("description", "")
                    row[3].text = issue.get("suggestion", "")
        
        # 总结
        if result.summary:
            doc.add_heading("审查总结", level=1)
            doc.add_paragraph(result.summary)
        
        # 页脚
        for section in doc.sections:
            footer = section.footer
            footer.add_paragraph(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
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