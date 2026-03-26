import argparse
import sys
from pathlib import Path
from typing import Optional, List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config.settings import settings
from models.document import ParsedDocument
from parsers.docx_parser import ParserFactory
from rules.base_rule import Rule, RuleRegistry, RuleCategory, RuleSeverity
from rules.loaders.rule_loader import RuleLoader
from llm.client import LLMClientFactory
from core.executor import ReviewExecutor, DocumentReviewResult
from reporters.base_reporter import ReporterFactory


console = Console()


class DocumentReviewer:
    def __init__(self, use_llm=True, llm_provider: Optional[str] = None):
        self.llm_client = None
        self.use_llm = use_llm
        self.llm_provider = llm_provider or settings.llm_provider
        
        # 初始化规则注册表
        self.rule_registry = RuleRegistry()
        # 加载默认规则
        self._load_default_rules()
        
        if self.use_llm:
            try:
                self.llm_client = LLMClientFactory.create_client(self.llm_provider)
            except Exception as e:
                console.print(f"[yellow]LLM客户端初始化失败: {e}[/yellow]")
                self.use_llm = False  # 安全标志
        
        self.executor = ReviewExecutor(
            rule_registry=self.rule_registry,
            llm_client=self.llm_client,
            use_llm=use_llm and self.llm_client is not None
        )
    
    def _load_default_rules(self):
        rules = RuleLoader.load_all_rules(profile="aviation")
        for rule in rules:
            self.rule_registry.register(rule)
    
    def add_rule(self, rule: Rule):
        self.rule_registry.register(rule)
    
    def add_rules(self, rules: List[Rule]):
        for rule in rules:
            self.rule_registry.register(rule)
    
    def enable_rule(self, rule_id: str):
        self.rule_registry.enable_rule(rule_id)
    
    def disable_rule(self, rule_id: str):
        self.rule_registry.disable_rule(rule_id)
    
    def review(self, file_path: str) -> DocumentReviewResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        parser = ParserFactory.get_parser(path.suffix)
        if not parser:
            raise ValueError(f"不支持的文件格式: {path.suffix}")
        
        console.print(f"[blue]正在解析文档: {file_path}[/blue]")
        document = parser.parse(str(path))
        console.print(f"[green]文档解析完成，共 {len(document.sections)} 个章节[/green]")
        
        console.print("[blue]正在执行审查...[/blue]")
        result = self.executor.review_document(document)
        console.print("[green]审查完成[/green]")
        
        return result
    
    def generate_report(
        self,
        result: DocumentReviewResult,
        output_path: str,
        format_type: str = "markdown"
    ):
        reporter = ReporterFactory.create_reporter(format_type)
        reporter.save(result, output_path)
        console.print(f"[green]报告已保存至: {output_path}[/green]")
    
    def print_summary(self, result: DocumentReviewResult):
        console.print()
        
        status_style = "green" if result.overall_passed else "red"
        status_text = "✅ 通过" if result.overall_passed else "❌ 未通过"
        
        console.print(Panel(
            f"文档: {result.document_title}\n"
            f"路径: {result.document_path}\n"
            f"耗时: {result.review_time}",
            title=f"审查结果: {status_text}",
            style=status_style
        ))
        
        table = Table(title="问题统计")
        table.add_column("类型", style="cyan")
        table.add_column("数量", justify="right")
        
        table.add_row("总问题", str(result.total_issues))
        table.add_row("错误", f"[red]{result.errors}[/red]")
        table.add_row("警告", f"[yellow]{result.warnings}[/yellow]")
        if hasattr(result, 'llm_issues') and result.llm_issues > 0:
            table.add_row("LLM问题", f"[blue]{result.llm_issues}[/blue]")
        
        console.print(table)
        
        if result.section_results:
            issues_table = Table(title="问题详情")
            issues_table.add_column("章节", style="cyan")
            issues_table.add_column("规则", style="magenta")
            issues_table.add_column("来源", style="green")
            issues_table.add_column("严重程度")
            issues_table.add_column("描述")
            
            for section_result in result.section_results:
                if not section_result.passed:
                    for rule_result in section_result.rule_results:
                        if not rule_result.passed:
                            severity_style = {
                                RuleSeverity.ERROR: "red",
                                RuleSeverity.WARNING: "yellow",
                                RuleSeverity.INFO: "blue"
                            }.get(rule_result.severity, "white")
                            
                            issues_table.add_row(
                                section_result.section_id,
                                rule_result.rule_name,
                                rule_result.rule_source,
                                f"[{severity_style}]{rule_result.severity.value}[/{severity_style}]",
                                rule_result.message[:50] + "..." if len(rule_result.message) > 50 else rule_result.message
                            )
            
            if issues_table.rows:
                console.print(issues_table)


def main():
    parser = argparse.ArgumentParser(
        description="文档审查智能体 - 利用大模型和规则审查文档"
    )
    parser.add_argument(
        "-i", "--input",
        help="要审查的文档路径",
        default=settings.default_document_path
    )
    parser.add_argument(
        "-o", "--output",
        help="报告输出路径",
        default=None
    )
    parser.add_argument(
        "-f", "--format",
        choices=["md", "json", "docx"],
        default="docx",
        help="报告格式 (md/json/docx)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="禁用LLM审查，仅使用规则"
    )
    parser.add_argument(
        "--provider",
        default="openai",
        help="LLM提供商"
    )
    
    args = parser.parse_args()
    
    # 打印使用的模型信息
    console.print(f"[blue]使用模型: {settings.llm_model}[/blue]")
    console.print(f"[blue]API 端点: {settings.llm_base_url}[/blue]")
    console.print()
    
    try:
        reviewer = DocumentReviewer(
            use_llm=not args.no_llm,
            llm_provider=args.provider
        )
        
        result = reviewer.review(args.input)
        
        reviewer.print_summary(result)
        
        import time
        
        if args.output:
            output_file = Path(args.output)
            if output_file.exists():
                try:
                    output_file.unlink()
                    console.print(f"[yellow]已删除存在的文件: {args.output}[/yellow]")
                except Exception as e:
                    # 如果文件被占用，使用时间戳生成新文件名
                    timestamp = int(time.time())
                    new_output_path = output_file.parent / f"{output_file.stem}_{timestamp}{output_file.suffix}"
                    console.print(f"[yellow]文件被占用，使用新文件名: {new_output_path}[/yellow]")
                    args.output = str(new_output_path)
            
            reviewer.generate_report(result, args.output, args.format)
        else:
            if args.format == "md":
                output_path = Path(args.input).stem + "_report.md"
            elif args.format == "json":
                output_path = Path(args.input).stem + "_report.json"
            elif args.format == "docx":
                output_path = Path(args.input).stem + "_report.docx"

            
            output_file = Path(output_path)
            if output_file.exists():
                try:
                    output_file.unlink()
                    console.print(f"[yellow]已删除存在的文件: {output_path}[/yellow]")
                except Exception as e:
                    # 如果文件被占用，使用时间戳生成新文件名
                    timestamp = int(time.time())
                    new_output_path = output_file.parent / f"{output_file.stem}_{timestamp}{output_file.suffix}"
                    console.print(f"[yellow]文件被占用，使用新文件名: {new_output_path}[/yellow]")
                    output_path = new_output_path
            
            reviewer.generate_report(result, str(output_path), args.format)
        
        sys.exit(0 if result.overall_passed else 1)
        
    except FileNotFoundError as e:
        console.print(f"[red]错误: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]发生错误: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()