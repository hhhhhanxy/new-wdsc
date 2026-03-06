#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试文档审查API
"""

import requests
import json

url = 'http://localhost:5000/api/review'
data = {
    'file_path': 'e:\\github\\new-wdsc\\test_document.txt'
}

try:
    response = requests.post(url, json=data)
    result = response.json()
    print(json.dumps(result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f'请求失败: {e}')
