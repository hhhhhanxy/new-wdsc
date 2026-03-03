import networkx as nx
import json
import os

class KnowledgeBase:
    def __init__(self, knowledge_path='data/knowledge'):
        self.knowledge_path = knowledge_path
        self.graph = nx.DiGraph()
        self.load_knowledge()
    
    def load_knowledge(self):
        """加载知识库"""
        if not os.path.exists(self.knowledge_path):
            os.makedirs(self.knowledge_path)
        
        # 加载领域知识
        knowledge_file = os.path.join(self.knowledge_path, 'domain_knowledge.json')
        if os.path.exists(knowledge_file):
            with open(knowledge_file, 'r', encoding='utf-8') as f:
                knowledge_data = json.load(f)
                for item in knowledge_data:
                    self.add_entity(item['entity'], item['attributes'], item['relations'])
    
    def add_entity(self, entity, attributes=None, relations=None):
        """添加实体到知识库"""
        self.graph.add_node(entity, **(attributes or {}))
        if relations:
            for relation, target in relations.items():
                self.graph.add_edge(entity, target, relation=relation)
    
    def get_entity(self, entity):
        """获取实体信息"""
        if entity in self.graph.nodes:
            return {
                'entity': entity,
                'attributes': self.graph.nodes[entity],
                'relations': [(neighbor, self.graph[entity][neighbor]['relation']) 
                            for neighbor in self.graph.neighbors(entity)]
            }
        return None
    
    def query_relations(self, entity, relation_type=None):
        """查询实体的关系"""
        relations = []
        if entity in self.graph.nodes:
            for neighbor in self.graph.neighbors(entity):
                rel = self.graph[entity][neighbor]['relation']
                if relation_type is None or rel == relation_type:
                    relations.append((neighbor, rel))
        return relations
    
    def save_knowledge(self):
        """保存知识库"""
        knowledge_data = []
        for node in self.graph.nodes:
            entity_data = {
                'entity': node,
                'attributes': self.graph.nodes[node],
                'relations': {}
            }
            for neighbor in self.graph.neighbors(node):
                entity_data['relations'][self.graph[node][neighbor]['relation']] = neighbor
            knowledge_data.append(entity_data)
        
        knowledge_file = os.path.join(self.knowledge_path, 'domain_knowledge.json')
        with open(knowledge_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge_data, f, ensure_ascii=False, indent=2)
    
    def search_knowledge(self, query):
        """搜索知识库"""
        results = []
        for node in self.graph.nodes:
            if query in node:
                results.append(self.get_entity(node))
        return results