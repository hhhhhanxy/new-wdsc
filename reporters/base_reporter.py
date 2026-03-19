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


class TextReporter(BaseReporter):
    def generate(self, result: DocumentReviewResult) -> str:
        lines = []
        
        lines.append("=" * 60)
        lines.append("文档审查报告")
        lines.append("=" * 60)
        lines.append("")
        
        lines.append(f"文档标题: {result.document_title}")
        lines.append(f"文档路径: {result.document_path}")
        lines.append(f"审查时间: {result.review_time}")
        lines.append(f"审查结果: {'通过' if result.overall_passed else '未通过'}")
        lines.append("")
        
        lines.append("-" * 60)
        lines.append("审查统计")
        lines.append("-" * 60)
        lines.append(f"总问题数: {result.total_issues}")
        lines.append(f"错误数: {result.errors}")
        lines.append(f"警告数: {result.warnings}")
        if hasattr(result, 'llm_issues') and result.llm_issues > 0:
            lines.append(f"LLM发现问题数: {result.llm_issues}")
        lines.append("")
        
        if result.summary:
            lines.append("-" * 60)
            lines.append("审查总结")
            lines.append("-" * 60)
            lines.append(result.summary)
            lines.append("")
        
        lines.append("-" * 60)
        lines.append("详细结果")
        lines.append("-" * 60)
        
        for section_result in result.section_results:
            if not section_result.passed:
                lines.append("")
                lines.append(f"[章节 {section_result.section_id}]")
                lines.append(f"内容: {section_result.section_text[:100]}...")
                lines.append(f"状态: {'通过' if section_result.passed else '未通过'}")
                
                for rule_result in section_result.rule_results:
                    if not rule_result.passed:
                        severity_str = {
                            RuleSeverity.ERROR: "错误",
                            RuleSeverity.WARNING: "警告",
                            RuleSeverity.INFO: "信息"
                        }.get(rule_result.severity, "未知")
                        
                        lines.append(f"  [{severity_str}] {rule_result.rule_name}")
                        lines.append(f"    {rule_result.message}")
                        
                        if rule_result.suggestions:
                            lines.append(f"    建议: {', '.join(rule_result.suggestions)}")
        
        lines.append("")
        lines.append("=" * 60)
        lines.append("报告生成完成")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def save(self, result: DocumentReviewResult, output_path: str):
        content = self.generate(result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)


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
                "warnings": result.warnings
            },
            "summary": result.summary,
            "sections": []
        }
        
        for section_result in result.section_results:
            section_data = {
                "section_id": section_result.section_id,
                "section_text": section_result.section_text,
                "passed": section_result.passed,
                "issues": []
            }
            
            for rule_result in section_result.rule_results:
                if not rule_result.passed:
                    issue_data = {
                        "rule_id": rule_result.rule_id,
                        "rule_name": rule_result.rule_name,
                        "severity": rule_result.severity.value,
                        "message": rule_result.message,
                        "suggestions": rule_result.suggestions
                    }
                    section_data["issues"].append(issue_data)
            
            if section_result.llm_review:
                section_data["llm_review"] = section_result.llm_review
            
            data["sections"].append(section_data)
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def save(self, result: DocumentReviewResult, output_path: str):
        content = self.generate(result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)


class DocxReporter(BaseReporter):
    def generate(self, result: DocumentReviewResult) -> Document:
        doc = Document()
        
        # 设置标题
        title = doc.add_heading('文档审查报告', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 添加基本信息
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
        
        # 添加审查统计
        doc.add_heading('审查统计', level=1)
        stats_table = doc.add_table(rows=3, cols=2)
        stats_table.style = 'Table Grid'
        
        stats_table.cell(0, 0).text = '总问题数'
        stats_table.cell(0, 1).text = str(result.total_issues)
        stats_table.cell(1, 0).text = '错误数'
        stats_table.cell(1, 1).text = str(result.errors)
        stats_table.cell(2, 0).text = '警告数'
        stats_table.cell(2, 1).text = str(result.warnings)
        
        if hasattr(result, 'llm_issues') and result.llm_issues > 0:
            row = stats_table.add_row()
            row.cells[0].text = 'LLM发现问题数'
            row.cells[1].text = str(result.llm_issues)
        
        # 按规则分组的详细结果
        doc.add_heading('详细结果（按规则分组）', level=1)
        
        # 收集所有规则
        rules = {}
        for section_result in result.section_results:
            for rule_result in section_result.rule_results:
                rule_id = rule_result.rule_id
                if rule_id not in rules:
                    rules[rule_id] = {
                        "name": rule_result.rule_name,
                        "issues": []
                    }
                if not rule_result.passed:
                    rules[rule_id]["issues"].append({
                        "section_id": section_result.section_id,
                        "section_text": section_result.section_text,
                        "message": rule_result.message,
                        "suggestions": rule_result.suggestions
                    })
        
        # 输出每条规则的结果
        for rule_id, rule_info in rules.items():
            rule_title = f"{rule_info['name']} ({len(rule_info['issues'])}个问题)"
            doc.add_heading(rule_title, level=2)
            
            if rule_info['issues']:
                for issue in rule_info['issues']:
                    doc.add_heading(f"章节: {issue['section_id']}", level=3)
                    doc.add_paragraph(f"内容: {issue['section_text'][:100]}...")
                    doc.add_paragraph(f"问题: {issue['message']}")
                    if issue['suggestions']:
                        doc.add_paragraph("建议:")
                        for suggestion in issue['suggestions']:
                            doc.add_paragraph(f"- {suggestion}", style='List Bullet')
            else:
                doc.add_paragraph("未发现问题")
        
        # 添加总结
        if result.summary:
            doc.add_heading('审查总结', level=1)
            doc.add_paragraph(result.summary)
        
        # 添加页脚
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
        "txt": TextReporter,
        "text": TextReporter,
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
