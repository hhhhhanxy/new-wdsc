#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试保存审查结果为文档的功能
"""

import requests
import json

url = 'http://localhost:5000/api/review'
data = {
    'file_path': 'e:\\github\\new-wdsc\\test_document.txt',
    'save_result': True  # 启用保存结果文档功能
}

try:
    response = requests.post(url, json=data)
    result = response.json()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    if 'result_document' in result:
        print(f'\n审查结果文档已保存到: {result["result_document"]}')
        print('您可以打开该文档查看详细的审查结果。')
except Exception as e:
    print(f'请求失败: {e}')
