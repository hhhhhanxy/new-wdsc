import requests
import json

url = 'http://localhost:5000/api/review'
data = {
    'file_path': 'C:\\Users\\DELL\\Desktop\\需求规格说明.docx'
}

try:
    response = requests.post(url, json=data)
    result = response.json()
    print(json.dumps(result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f'请求失败: {e}')
