# import spacy

class NLPService:
    def __init__(self):
        # 暂时注释掉spaCy的加载
        # try:
        #     self.nlp = spacy.load('zh_core_web_sm')
        # except:
        #     # 如果模型不存在，使用英文模型作为备选
        #     self.nlp = spacy.load('en_core_web_sm')
        self.nlp = None
    
    def extract_entities(self, text):
        """提取文本中的实体"""
        # 简化实现
        return []
    
    def extract_keywords(self, text):
        """提取文本中的关键词"""
        # 简化实现
        return text.split()[:20]
    
    def analyze_sentiment(self, text):
        """分析文本情感"""
        # 简化实现，实际项目中可使用更专业的情感分析工具
        positive_words = ['好', '优秀', '成功', '正确', '合规']
        negative_words = ['错误', '失败', '违规', '缺陷', '问题']
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def parse_sentences(self, text):
        """解析文本中的句子"""
        # 简化实现
        return text.split('。')