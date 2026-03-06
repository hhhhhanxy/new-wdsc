#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审查规则示例

展示如何使用审查规则框架添加、删除和修改审查规则。
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.review_framework import (
    ReviewRule, FormatRule, ContentRule, TerminologyRule, ComplianceRule, LanguageRule,
    rule_manager
)
import re

# 1. 格式规则类
class PunctuationRule(FormatRule):
    """标点符号使用规则"""
    
    def check(self, text, rules):
        """检查标点符号使用"""
        issues = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            # 检查中英文标点混用
            if re.search(r'[a-zA-Z0-9]，|，[a-zA-Z0-9]', line):
                issues.append(f'第{i+1}行：中英文混用时标点符号使用不当')
            # 检查行尾空格
            if line.rstrip() != line:
                issues.append(f'第{i+1}行：行尾存在多余空格')
            # 检查连续标点
            if re.search(r'[，。；：！？]{2,}', line):
                issues.append(f'第{i+1}行：存在连续标点符号')
        
        return issues

class NumberUnitRule(FormatRule):
    """数字和单位格式规则"""
    
    def check(self, text, rules):
        """检查数字和单位格式"""
        issues = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            # 检查数字与单位之间是否有空格
            if re.search(r'\d+[a-zA-Z%℃°]', line):
                issues.append(f'第{i+1}行：数字与单位之间缺少空格')
            # 检查小数点使用
            if re.search(r'\d+，\d+', line):
                issues.append(f'第{i+1}行：使用了中文逗号作为小数点')
        
        return issues

class ParagraphFormatRule(FormatRule):
    """段落格式规则"""
    
    def check(self, text, rules):
        """检查段落格式"""
        issues = []
        lines = text.split('\n')
        
        empty_line_count = 0
        for i, line in enumerate(lines):
            if line.strip() == '':
                empty_line_count += 1
                if empty_line_count > 2:
                    issues.append(f'第{i+1}行：存在连续多个空行')
            else:
                empty_line_count = 0
        
        return issues

class CitationFormatRule(FormatRule):
    """引用格式规则"""
    
    def check(self, text, rules):
        """检查引用格式"""
        issues = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if re.search(r'\[\d+\]', line):
                # 检查引用编号格式
                if not re.search(r'\[\d+\]$', line.strip()):
                    issues.append(f'第{i+1}行：引用编号位置不当')
        
        return issues

class CodeBlockRule(FormatRule):
    """代码块格式规则"""
    
    def check(self, text, rules):
        """检查代码块格式"""
        issues = []
        lines = text.split('\n')
        
        in_code_block = False
        for i, line in enumerate(lines):
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
            elif in_code_block:
                # 检查代码缩进
                if line.startswith('\t'):
                    issues.append(f'第{i+1}行：代码块中使用了制表符缩进，建议使用空格')
        
        return issues

class TableFormatRule(FormatRule):
    """表格格式规则"""
    
    def check(self, text, rules):
        """检查表格格式"""
        issues = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if '|' in line:
                # 简单检查表格格式
                if not re.match(r'^\|.*\|$', line.strip()):
                    issues.append(f'第{i+1}行：表格格式不正确')
        
        return issues

# 2. 内容规则类
class SectionOrderRule(ContentRule):
    """章节顺序规则"""
    
    def check(self, text, rules):
        """检查章节顺序"""
        issues = []
        # 检查章节顺序是否符合逻辑
        standard_order = ['摘要', '引言', '设计方案', '验证结果', '结论']
        
        # 提取文档中的章节顺序
        found_sections = []
        lines = text.split('\n')
        for line in lines:
            for section in standard_order:
                if section in line and section not in found_sections:
                    found_sections.append(section)
        
        # 检查顺序是否正确
        for i, section in enumerate(found_sections):
            if i < len(standard_order) and section != standard_order[i]:
                issues.append(f'章节顺序不正确：{section} 应该在 {standard_order[i]} 之后')
                break
        
        return issues

class ContentCoverageRule(ContentRule):
    """内容覆盖度规则"""
    
    def check(self, text, rules):
        """检查内容覆盖度"""
        issues = []
        # 检查是否覆盖所有必要内容
        required_contents = rules.get('required_contents', [])
        
        for content in required_contents:
            if content not in text:
                issues.append(f'缺少必要内容：{content}')
        
        return issues

class CitationIntegrityRule(ContentRule):
    """引用完整性规则"""
    
    def check(self, text, rules):
        """检查引用完整性"""
        issues = []
        # 检查引用是否完整
        citations = re.findall(r'\[\d+\]', text)
        
        if not citations:
            issues.append('文档中没有引用')
        
        return issues

# 3. 术语规则类
class TechnicalTermRule(TerminologyRule):
    """专业术语使用规则"""
    
    def check(self, text, rules):
        """检查专业术语使用"""
        issues = []
        # 检查专业术语使用是否正确
        technical_terms = rules.get('technical_terms', [])
        
        for term in technical_terms:
            if term not in text:
                issues.append(f'缺少专业术语：{term}')
        
        return issues

# 4. 合规性规则类
class ComplianceStatementRule(ComplianceRule):
    """合规性声明规则"""
    
    def check(self, text, rules):
        """检查合规性声明"""
        issues = []
        # 检查是否包含必要的合规性声明
        required_statements = rules.get('required_statements', [])
        
        for statement in required_statements:
            if statement not in text:
                issues.append(f'缺少合规性声明：{statement}')
        
        return issues

# 5. 语言规则类
class GrammarSpellingRule(LanguageRule):
    """语法和拼写规则"""
    
    def check(self, text, rules):
        """检查语法和拼写"""
        issues = []
        # 简单检查常见拼写错误
        common_misspellings = {
            '作动器': ['作动气', '做动器'],
            '控制系统': ['控制系通', '控制系统']
        }
        
        for correct, misspellings in common_misspellings.items():
            for misspelling in misspellings:
                if misspelling in text:
                    issues.append(f'拼写错误：{misspelling} 应该为 {correct}')
        
        return issues

class ProfessionalLanguageRule(LanguageRule):
    """专业语言规则"""
    
    def check(self, text, rules):
        """检查专业语言使用"""
        issues = []
        # 检查是否使用专业语言
        unprofessional_expressions = ['觉得', '感觉', '好像', '应该', '可能']
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            for expr in unprofessional_expressions:
                if expr in line:
                    issues.append(f'第{i+1}行：使用了非专业表达 "{expr}"，建议使用更专业的表述')
        
        return issues

# 添加18条审查规则
def add_all_rules():
    """添加所有18条审查规则"""
    
    # 1. 格式规则（6条）
    rule_manager.add_rule(PunctuationRule('punctuation', '标点符号使用检查', 1))
    rule_manager.add_rule(NumberUnitRule('number_unit', '数字和单位格式检查', 2))
    rule_manager.add_rule(ParagraphFormatRule('paragraph_format', '段落格式检查', 3))
    rule_manager.add_rule(CitationFormatRule('citation_format', '引用格式检查', 4))
    rule_manager.add_rule(CodeBlockRule('code_block', '代码块格式检查', 5))
    rule_manager.add_rule(TableFormatRule('table_format', '表格格式检查', 6))
    
    # 2. 内容规则（4条）
    rule_manager.add_rule(SectionOrderRule('section_order', '章节顺序检查', 7))
    rule_manager.add_rule(ContentCoverageRule('content_coverage', '内容覆盖度检查', 8))
    rule_manager.add_rule(CitationIntegrityRule('citation_integrity', '引用完整性检查', 9))
    
    # 3. 术语规则（2条）
    rule_manager.add_rule(TechnicalTermRule('technical_term', '专业术语使用检查', 10))
    
    # 4. 合规性规则（2条）
    rule_manager.add_rule(ComplianceStatementRule('compliance_statement', '合规性声明检查', 11))
    
    # 5. 语言规则（4条）
    rule_manager.add_rule(GrammarSpellingRule('grammar_spelling', '语法和拼写检查', 12))
    rule_manager.add_rule(ProfessionalLanguageRule('professional_language', '专业语言检查', 13))
    
    # 显示已添加的规则
    print(f'已添加 {len(rule_manager.rules)} 条审查规则：')
    for rule in rule_manager.rules:
        print(f'- {rule.name}: {rule.description} (优先级: {rule.priority})')

# 测试规则
def test_rules():
    """测试审查规则"""
    # 创建测试文本
    test_text = """
# 技术文档测试

## 摘要
这是一份技术文档测试文件，用于测试文档审查功能。

## 引言
本文档旨在测试文档审查系统的各项功能，包括格式检查、内容完整性检查、术语一致性检查和合规性检查。

## 设计方案
本设计方案采用了先进的技术架构，包括作动器、控制系统等核心组件。

## 验证结果
验证结果表明，系统性能符合预期要求。

## 结论
本系统设计合理，性能优越，达到了预期目标。

### 技术参数
- 工作温度：-40℃~85℃
- 工作电压：24V
- 最大负载：100kg

## 参考标准
- GB/T 19001
- AS9100
- GJB 9001C
"""
    
    # 测试规则
    rules = {
        'required_sections': ['摘要', '引言', '设计方案', '验证结果', '结论'],
        'required_standards': ['GB/T 19001', 'AS9100', 'GJB 9001C'],
        'technical_terms': ['作动器', '控制系统'],
        'required_contents': ['设计方案', '验证结果'],
        'required_statements': ['本系统符合相关标准要求']
    }
    
    # 执行审查
    results = rule_manager.execute_rules(test_text, rules)
    
    # 显示结果
    print('\n审查结果：')
    for category, issues in results.items():
        if issues:
            print(f'\n{category}：')
            for issue in issues:
                print(f'- {issue}')
        else:
            print(f'\n{category}：无问题')

if __name__ == '__main__':
    # 添加所有规则
    add_all_rules()
    
    # 测试规则
    test_rules()
    
    # 示例：删除规则
    print('\n示例：删除规则')
    rule_manager.remove_rule('punctuation')
    print(f'删除后剩余 {len(rule_manager.rules)} 条规则')
    
    # 示例：添加规则
    print('\n示例：添加规则')
    rule_manager.add_rule(PunctuationRule('punctuation', '标点符号使用检查', 1))
    print(f'添加后共有 {len(rule_manager.rules)} 条规则')
