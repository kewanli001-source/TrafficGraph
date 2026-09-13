"""embedding — 交通知识库离线向量器与可选 BGE 适配

所属层：knowledge
依赖：chromadb, hashlib
对接算法层：本地向量检索
"""
import hashlib
import math
import os
import re
from typing import Any, Dict, List, Optional

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from chromadb.utils.embedding_functions import register_embedding_function

_DIMENSION = 384


def _tokens(text: str) -> List[str]:
    """把中英文文本拆成字符、双字词和英文单词。

    Args:
        text: 原始文本。

    Returns:
        可用于特征哈希的 token 列表。
    """
    normalized = re.sub(r"\s+", "", str(text or "")).lower()
    tokens = list(normalized)
    tokens.extend(normalized[index:index + 2] for index in range(len(normalized) - 1))
    tokens.extend(re.findall(r"[a-z0-9_.+-]+", str(text or "").lower()))
    return tokens or ["empty"]


@register_embedding_function
class TrafficHashEmbeddingFunction(EmbeddingFunction[Documents]):
    """无需外网下载即可运行的确定性特征哈希向量器。

    该向量器面向小规模交通专业语料和离线演示，使用字符/双字词特征哈希，
    不依赖 Hugging Face。需要更高检索质量时，可切换 BGE 后端。
    """

    def __init__(self, dimension: int = _DIMENSION) -> None:
        """初始化向量维度。

        Args:
            dimension: 向量维度。
        """
        self.dimension = dimension

    def __call__(self, input: Documents) -> Embeddings:
        """把文本转换为归一化向量。

        Args:
            input: 待编码文本列表。

        Returns:
            与输入等长的向量列表。
        """
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> List[float]:
        """生成单条文本向量。

        Args:
            text: 待编码文本。

        Returns:
            归一化后的浮点向量。
        """
        vector = [0.0] * self.dimension
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def name() -> str:
        """返回 Chroma 向量器名称。"""
        return "traffic_hash"

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "TrafficHashEmbeddingFunction":
        """从持久化配置恢复向量器。"""
        return TrafficHashEmbeddingFunction(dimension=int(config.get("dimension", _DIMENSION)))

    def get_config(self) -> Dict[str, Any]:
        """返回可序列化配置。"""
        return {"dimension": self.dimension}


def get_embedding_function(
    backend: Optional[str] = None,
) -> EmbeddingFunction[Documents]:
    """创建交通知识库向量器。

    Args:
        backend: 可选覆盖后端；默认读取 TRAFFIC_EMBEDDING_BACKEND。

    Returns:
        Chroma EmbeddingFunction。默认 hashing 可完全离线运行；
        backend=bge 时使用 BAAI/bge-small-zh-v1.5。

    Raises:
        ValueError: 配置了不支持的向量后端。
        ImportError: BGE 依赖未安装。
    """
    selected = (backend or os.getenv("TRAFFIC_EMBEDDING_BACKEND", "hashing")).strip().lower()
    if selected in {"hashing", "hash", "offline"}:
        return TrafficHashEmbeddingFunction()
    if selected in {"bge", "sentence-transformers", "sentence_transformers"}:
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        except ImportError as exc:
            raise ImportError("BGE 向量后端需要 sentence-transformers") from exc
        return SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-small-zh-v1.5")
    raise ValueError(
        f"不支持的 TRAFFIC_EMBEDDING_BACKEND={selected}，可选 hashing 或 bge"
    )
