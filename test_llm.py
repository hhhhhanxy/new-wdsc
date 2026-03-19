"""测试 SiliconFlow LLM API 调用"""
import os
from dotenv import load_dotenv
from openai import OpenAI
from config.settings import settings

# 加载环境变量
load_dotenv()

# 从配置文件获取配置
api_key = settings.llm_api_key
base_url = settings.llm_base_url
model = settings.llm_model

print(f"API Base URL: {base_url}")
print(f"Model: {model}")
print(f"API Key: {'已设置' if api_key and api_key != 'your_api_key_here' else '未设置'}")

if api_key and api_key != "your_api_key_here":
    try:
        # 创建客户端
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        # 发送请求
        print("\n正在发送请求...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个有用的助手"},
                {"role": "user", "content": "你好，请介绍一下你自己"}
            ],
            max_tokens=4096,
            temperature=0.1
        )
        
        # 输出结果
        print("\n=== 响应结果 ===")
        print(f"模型: {response.model}")
        print(f"内容: {response.choices[0].message.content}")
        print(f"\nToken 使用:")
        print(f"  - 提示词: {response.usage.prompt_tokens}")
        print(f"  - 生成: {response.usage.completion_tokens}")
        print(f"  - 总计: {response.usage.total_tokens}")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n请先设置 API Key 到 .env 文件中")