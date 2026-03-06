import os
import json
import hashlib

from app.utils.config import config

def ensure_dir(directory):
    """确保目录存在"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def get_file_hash(file_path):
    """获取文件哈希值"""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def load_json_file(file_path):
    """加载JSON文件"""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json_file(file_path, data):
    """保存JSON文件"""
    ensure_dir(os.path.dirname(file_path))
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def validate_file_format(file_path, allowed_formats=['.pdf', '.docx']):
    """验证文件格式"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in allowed_formats

def get_file_size(file_path):
    """获取文件大小（字节）"""
    if os.path.exists(file_path):
        return os.path.getsize(file_path)
    return 0

def format_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def generate_unique_id():
    """生成唯一ID"""
    import uuid
    return str(uuid.uuid4())

def update_review_rules(updates=None):
    """
    更新审查规则
    :param updates: 要更新的规则字典，包含以下可选键：
        - required_sections: 新的必填章节列表
        - required_standards: 新的必须遵循的标准列表
        - terminology_standards: 新的术语标准
        - format_rules: 新的格式规则
    :return: 更新后的规则
    """
    from app.utils.config import config
    
    # 规则文件路径
    rules_file = os.path.join(config.RULES_DIR, 'review_rules.json')
    
    # 加载现有规则
    current_rules = load_json_file(rules_file)
    
    # 如果没有提供更新，则返回当前规则
    if not updates:
        return current_rules
    
    # 更新规则
    if 'required_sections' in updates:
        current_rules['required_sections'] = updates['required_sections']
    
    if 'required_standards' in updates:
        current_rules['required_standards'] = updates['required_standards']
    
    if 'terminology_standards' in updates:
        current_rules['terminology_standards'] = updates['terminology_standards']
    
    if 'format_rules' in updates:
        # 如果是完整替换
        if isinstance(updates['format_rules'], dict):
            current_rules['format_rules'] = updates['format_rules']
        # 如果是部分更新
        elif isinstance(updates['format_rules'], dict):
            for key, value in updates['format_rules'].items():
                if key in current_rules['format_rules']:
                    if isinstance(current_rules['format_rules'][key], dict) and isinstance(value, dict):
                        current_rules['format_rules'][key].update(value)
                    else:
                        current_rules['format_rules'][key] = value
    
    # 保存更新后的规则
    save_json_file(rules_file, current_rules)
    
    return current_rules

def add_review_rule(rule_type, rule_value):
    """
    添加单个审查规则
    :param rule_type: 规则类型，可选值：
        - section: 添加必填章节
        - standard: 添加必须遵循的标准
        - terminology: 更新术语标准
        - font_size: 添加字体大小规则
        - line_spacing: 更新行间距
        - margin: 更新页边距
    :param rule_value: 规则值
    :return: 更新后的规则
    """
    from app.utils.config import config
    
    # 规则文件路径
    rules_file = os.path.join(config.RULES_DIR, 'review_rules.json')
    
    # 加载现有规则
    current_rules = load_json_file(rules_file)
    
    # 根据规则类型添加规则
    if rule_type == 'section':
        if 'required_sections' not in current_rules:
            current_rules['required_sections'] = []
        if rule_value not in current_rules['required_sections']:
            current_rules['required_sections'].append(rule_value)
    
    elif rule_type == 'standard':
        if 'required_standards' not in current_rules:
            current_rules['required_standards'] = []
        if rule_value not in current_rules['required_standards']:
            current_rules['required_standards'].append(rule_value)
    
    elif rule_type == 'terminology':
        current_rules['terminology_standards'] = rule_value
    
    elif rule_type == 'font_size':
        if 'format_rules' not in current_rules:
            current_rules['format_rules'] = {}
        if 'font_size' not in current_rules['format_rules']:
            current_rules['format_rules']['font_size'] = {}
        # 假设rule_value是一个字典，如{"小标题": 14}
        if isinstance(rule_value, dict):
            current_rules['format_rules']['font_size'].update(rule_value)
    
    elif rule_type == 'line_spacing':
        if 'format_rules' not in current_rules:
            current_rules['format_rules'] = {}
        current_rules['format_rules']['line_spacing'] = rule_value
    
    elif rule_type == 'margin':
        if 'format_rules' not in current_rules:
            current_rules['format_rules'] = {}
        if 'margin' not in current_rules['format_rules']:
            current_rules['format_rules']['margin'] = {}
        # 假设rule_value是一个字典，如{"top": 3.0}
        if isinstance(rule_value, dict):
            current_rules['format_rules']['margin'].update(rule_value)
    
    # 保存更新后的规则
    save_json_file(rules_file, current_rules)
    
    return current_rules