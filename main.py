import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 尝试导入Flask，如果失败则退出
try:
    from flask import Flask
    from flask_restful import Api
    from app.modules.document_parser import DocumentParser
    from app.modules.document_generator import DocumentGenerator
    from app.modules.document_reviewer import DocumentReviewer
    
    app = Flask(__name__)
    api = Api(app)
    
    # 注册API路由
    api.add_resource(DocumentParser, '/api/parse')
    api.add_resource(DocumentGenerator, '/api/generate')
    api.add_resource(DocumentReviewer, '/api/review')
    
    if __name__ == '__main__':
        print("服务启动中...")
        app.run(debug=True, host='0.0.0.0', port=5000)
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖:")
    print("pip install Flask Flask-RESTful PyPDF2 python-docx networkx python-dotenv")
    sys.exit(1)