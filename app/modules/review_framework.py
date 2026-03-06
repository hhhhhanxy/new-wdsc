#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档审查规则框架

设计一个灵活的审查规则框架，方便管理和扩展审查规则。
"""

import os
import json
from abc import ABC, abstractmethod

class ReviewRule(ABC):
    """审查规则基类"""
    
    def __init__(self, name, description, priority=1):
        """
        初始化审查规则
        :param name: 规则名称
        :param description: 规则描述
        :param priority: 优先级，数字越小优先级越高
        """
        self.name = name
        self.description = description
        self.priority = priority
    
    @abstractmethod
    def check(self, text, rules):
        """
        执行审查
        :param text: 文档文本
        :param rules: 审查规则配置
        :return: 审查结果列表
        """
        pass

class FormatRule(ReviewRule):
    """格式规则基类"""
    pass

class ContentRule(ReviewRule):
    """内容规则基类"""
    pass

class TerminologyRule(ReviewRule):
    """术语规则基类"""
    pass

class ComplianceRule(ReviewRule):
    """合规性规则基类"""
    pass

class LanguageRule(ReviewRule):
    """语言规则基类"""
    pass

class ReviewRuleManager:
    """审查规则管理器"""
    
    def __init__(self):
        """初始化规则管理器"""
        self.rules = []
        self.rule_categories = {
            'format': [],
            'content': [],
            'terminology': [],
            'compliance': [],
            'language': []
        }
    
    def add_rule(self, rule):
        """
        添加审查规则
        :param rule: 审查规则对象
        """
        self.rules.append(rule)
        # 根据规则类型分类
        if isinstance(rule, FormatRule):
            self.rule_categories['format'].append(rule)
        elif isinstance(rule, ContentRule):
            self.rule_categories['content'].append(rule)
        elif isinstance(rule, TerminologyRule):
            self.rule_categories['terminology'].append(rule)
        elif isinstance(rule, ComplianceRule):
            self.rule_categories['compliance'].append(rule)
        elif isinstance(rule, LanguageRule):
            self.rule_categories['language'].append(rule)
        # 按优先级排序
        self.rules.sort(key=lambda x: x.priority)
        for category in self.rule_categories.values():
            category.sort(key=lambda x: x.priority)
    
    def remove_rule(self, rule_name):
        """
        删除审查规则
        :param rule_name: 规则名称
        :return: 是否删除成功
        """
        for rule in self.rules:
            if rule.name == rule_name:
                self.rules.remove(rule)
                # 从分类中删除
                for category in self.rule_categories.values():
                    for cat_rule in category:
                        if cat_rule.name == rule_name:
                            category.remove(cat_rule)
                            break
                return True
        return False
    
    def get_rule(self, rule_name):
        """
        获取审查规则
        :param rule_name: 规则名称
        :return: 审查规则对象
        """
        for rule in self.rules:
            if rule.name == rule_name:
                return rule
        return None
    
    def execute_rules(self, text, rules_config):
        """
        执行所有审查规则
        :param text: 文档文本
        :param rules_config: 规则配置
        :return: 审查结果
        """
        results = {
            'format_check': [],
            'content_check': [],
            'terminology_check': [],
            'compliance_check': [],
            'language_check': []
        }
        
        # 执行格式规则
        for rule in self.rule_categories['format']:
            issues = rule.check(text, rules_config)
            results['format_check'].extend(issues)
        
        # 执行内容规则
        for rule in self.rule_categories['content']:
            issues = rule.check(text, rules_config)
            results['content_check'].extend(issues)
        
        # 执行术语规则
        for rule in self.rule_categories['terminology']:
            issues = rule.check(text, rules_config)
            results['terminology_check'].extend(issues)
        
        # 执行合规性规则
        for rule in self.rule_categories['compliance']:
            issues = rule.check(text, rules_config)
            results['compliance_check'].extend(issues)
        
        # 执行语言规则
        for rule in self.rule_categories['language']:
            issues = rule.check(text, rules_config)
            results['language_check'].extend(issues)
        
        return results
    
    def save_rules(self, file_path):
        """
        保存规则配置
        :param file_path: 保存路径
        """
        rules_data = []
        for rule in self.rules:
            rule_data = {
                'name': rule.name,
                'description': rule.description,
                'priority': rule.priority,
                'type': rule.__class__.__name__
            }
            rules_data.append(rule_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
    
    def load_rules(self, file_path):
        """
        加载规则配置
        :param file_path: 配置文件路径
        """
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
            
            # 这里需要根据规则类型创建对应的规则对象
            # 实际实现时需要根据具体规则类进行映射
            pass

# 示例规则实现
class HeadingFormatRule(FormatRule):
    """标题格式规则"""
    
    def check(self, text, rules):
        """检查标题格式"""
        issues = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                # 检查标题层级
                heading_level = len([c for c in line if c == '#'])
                if heading_level > 6:
                    issues.append(f'第{i+1}行：标题层级超过6级')
                # 检查标题后是否有空格
                if not line.strip().startswith('# '):
                    issues.append(f'第{i+1}行：标题符号后缺少空格')
        
        return issues

class RequiredSectionsRule(ContentRule):
    """必要章节规则"""
    
    def check(self, text, rules):
        """检查必要章节"""
        issues = []
        required_sections = rules.get('required_sections', ['摘要', '引言', '结论'])
        
        for section in required_sections:
            if section not in text:
                issues.append(f'缺少必要章节：{section}')
        
        return issues

class TerminologyConsistencyRule(TerminologyRule):
    """术语一致性规则"""
    
    def check(self, text, rules):
        """检查术语一致性"""
        issues = []
        terminology_map = {
            '作动器': ['执行器', '驱动器'],
            '控制系统': ['控制回路']
        }
        
        for term, variations in terminology_map.items():
            if term in text:
                for variation in variations:
                    if variation != term and variation in text:
                        issues.append(f'术语不一致：{term} 与 {variation} 混用')
        
        return issues

class StandardsComplianceRule(ComplianceRule):
    """标准合规性规则"""
    
    def check(self, text, rules):
        """检查标准引用"""
        issues = []
        required_standards = rules.get('required_standards', [])
        
        for standard in required_standards:
            if standard not in text:
                issues.append(f'缺少标准引用：{standard}')
        
        return issues

class LanguageStyleRule(LanguageRule):
    """语言风格规则"""
    
    def check(self, text, rules):
        """检查语言风格"""
        issues = []
        # 检查口语化表达
        colloquial_expressions = ['觉得', '感觉', '好像', '应该', '可能']
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            for expr in colloquial_expressions:
                if expr in line:
                    issues.append(f'第{i+1}行：使用了口语化表达 "{expr}"，建议使用更专业的表述')
        
        return issues

# 规则管理器实例
def create_rule_manager():
    """创建规则管理器并添加默认规则"""
    manager = ReviewRuleManager()
    
    # 添加默认规则
    manager.add_rule(HeadingFormatRule('heading_format', '标题格式检查', 1))
    manager.add_rule(RequiredSectionsRule('required_sections', '必要章节检查', 2))
    manager.add_rule(TerminologyConsistencyRule('terminology_consistency', '术语一致性检查', 3))
    manager.add_rule(StandardsComplianceRule('standards_compliance', '标准合规性检查', 4))
    manager.add_rule(LanguageStyleRule('language_style', '语言风格检查', 5))
    
    return manager

# 全局规则管理器实例
rule_manager = create_rule_manager()
