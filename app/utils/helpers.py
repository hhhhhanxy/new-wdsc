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