from flask_restful import Resource, reqparse
import os
from docx import Document
import re

class DocumentReviewer(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('file_path', type=str, required=True, help='文档路径')
        parser.add_argument('rules', type=dict, required=False, help='审查规则')
        args = parser.parse_args()
        
        file_path = args['file_path']
<<<<<<< HEAD
        rules = args.get('rules') or {}
=======
        rules = args.get('rules', {})
>>>>>>> 13371a631da68f7aee494143cce0048891b48353
        
        # 确保路径是绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            return {'error': '文件不存在'}, 404
        
        try:
            review_results = self.review_document(file_path, rules)
            return {'status': 'success', 'results': review_results}, 200
        except Exception as e:
            return {'error': str(e)}, 500
    
    def review_document(self, file_path, rules):
        """审查文档"""
        results = {
            'format_check': [],
            'content_check': [],
            'terminology_check': [],
            'compliance_check': []
        }
        
        if file_path.endswith('.docx'):
            doc = Document(file_path)
            text = '\n'.join([p.text for p in doc.paragraphs])
        else:
            # 对于其他格式，这里简化处理
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        
        # 格式规范检查
        results['format_check'].extend(self.check_format(text))
        
        # 内容完整性校验
        results['content_check'].extend(self.check_content_integrity(text, rules))
        
        # 工程术语一致性分析
        results['terminology_check'].extend(self.check_terminology_consistency(text))
        
        # 合规性验证
        results['compliance_check'].extend(self.check_compliance(text, rules))
        
        return results
    
    def check_format(self, text):
        """检查格式规范"""
        issues = []
        
        # 检查标题格式
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                # 简单检查标题层级
                if len(re.findall('#', line)) > 6:
                    issues.append(f'第{i+1}行：标题层级超过6级')
        
        return issues
    
    def check_content_integrity(self, text, rules):
        """检查内容完整性"""
        issues = []
        
        # 检查必要章节
        required_sections = rules.get('required_sections', ['摘要', '引言', '结论'])
        for section in required_sections:
            if section not in text:
                issues.append(f'缺少必要章节：{section}')
        
        return issues
    
    def check_terminology_consistency(self, text):
        """检查工程术语一致性"""
        issues = []
        
        # 简单检查术语一致性（示例）
        terminology_map = {
            '作动器': ['执行器', '驱动器'],
            '控制系统': ['控制回路', '控制系统']
        }
        
        for term, variations in terminology_map.items():
            count = text.count(term)
            for variation in variations:
                if variation in text:
                    issues.append(f'术语不一致：{term} 与 {variation} 混用')
        
        return issues
    
    def check_compliance(self, text, rules):
        """检查合规性"""
        issues = []
        
        # 检查标准引用
        required_standards = rules.get('required_standards', [])
        for standard in required_standards:
            if standard not in text:
                issues.append(f'缺少标准引用：{standard}')
        
        return issues