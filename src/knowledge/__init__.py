"""knowledge — 交通知识库基础设施

所属层：knowledge
依赖：chromadb
对接算法层：本地向量检索
"""
from src.knowledge.embedding import get_embedding_function

__all__ = ["get_embedding_function"]
