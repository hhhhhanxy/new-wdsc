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
        rules = args.get('rules', {})
        
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
        
        # 确保rules是字典
        if rules is None:
            rules = {}
        
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
        
        lines = text.split('\n')
        
        # 检查标题格式
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                # 检查标题层级
                heading_level = len(re.findall('#', line))
                if heading_level > 6:
                    issues.append(f'第{i+1}行：标题层级超过6级')
                # 检查标题后是否有空格
                if not re.match(r'^#{1,6}\s+', line):
                    issues.append(f'第{i+1}行：标题符号后缺少空格')
        
        # 检查标点符号使用
        for i, line in enumerate(lines):
            # 检查中文标点使用
            if re.search(r'[a-zA-Z0-9]，|，[a-zA-Z0-9]', line):
                issues.append(f'第{i+1}行：中英文混用时标点符号使用不当')
            # 检查行尾空格
            if line.rstrip() != line:
                issues.append(f'第{i+1}行：行尾存在多余空格')
            # 检查连续标点
            if re.search(r'[，。；：！？]{2,}', line):
                issues.append(f'第{i+1}行：存在连续标点符号')
        
        # 检查数字和单位格式
        for i, line in enumerate(lines):
            # 检查数字与单位之间是否有空格
            if re.search(r'\d+[a-zA-Z%℃°]', line):
                issues.append(f'第{i+1}行：数字与单位之间缺少空格')
            # 检查小数点使用
            if re.search(r'\d+，\d+', line):
                issues.append(f'第{i+1}行：使用了中文逗号作为小数点')
        
        # 检查段落格式
        empty_line_count = 0
        for i, line in enumerate(lines):
            if line.strip() == '':
                empty_line_count += 1
                if empty_line_count > 2:
                    issues.append(f'第{i+1}行：存在连续多个空行')
            else:
                empty_line_count = 0
        
        # 检查引用格式
        for i, line in enumerate(lines):
            if re.search(r'\[\d+\]', line):
                # 检查引用编号格式
                if not re.search(r'\[\d+\]$', line.strip()):
                    issues.append(f'第{i+1}行：引用编号位置不当')
        
        # 检查代码块格式
        in_code_block = False
        for i, line in enumerate(lines):
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
            elif in_code_block:
                # 检查代码缩进
                if line.startswith('    '):
                    pass  # 4空格缩进，符合规范
                elif line.startswith('\t'):
                    issues.append(f'第{i+1}行：代码块中使用了制表符缩进，建议使用空格')
        
        # 检查表格格式
        for i, line in enumerate(lines):
            if '|' in line:
                # 简单检查表格格式
                if not re.match(r'^\|.*\|$', line.strip()):
                    issues.append(f'第{i+1}行：表格格式不正确')
        
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
            '控制系统': ['控制回路']
        }
        
        for term, variations in terminology_map.items():
            count = text.count(term)
            for variation in variations:
                if variation != term and variation in text:
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