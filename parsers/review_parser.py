# 用于解析 LLM 输出的 JSON 格式结果
import json

class ReviewResultParser:
    """解析 LLM 输出的审查结果 JSON"""

    def parse(self, text: str) -> dict:
        """
        尝试将文本解析为 JSON，如果失败则返回原始文本
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 简单兜底
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end+1])
                except json.JSONDecodeError:
                    pass
            
            return {"raw": text}