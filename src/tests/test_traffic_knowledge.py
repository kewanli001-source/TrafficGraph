"""test_traffic_knowledge — 交通语料与离线向量器测试

所属层：tests
依赖：pytest, src.knowledge, src.pipelines.rag_ingest
对接算法层：本地 ChromaDB 知识检索
"""
import math
from pathlib import Path

from src.knowledge import get_embedding_function
from src.pipelines.rag_ingest import _classify_system, _load_rows

CORPUS_PATH = Path(__file__).resolve().parents[2] / "data" / "traffic_qa_corpus.jsonl"


def test_traffic_corpus_loads():
    """交通语料可解析且覆盖主要业务类别。"""
    rows = _load_rows(CORPUS_PATH)
    categories = {_classify_system(system) for system, _, _ in rows}

    assert len(rows) >= 50
    assert {"signal", "incident", "dispatch", "standard", "flow"} <= categories


def test_offline_embedding_is_deterministic_and_normalized():
    """离线向量器输出稳定、维度固定且模长为 1。"""
    embedding_function = get_embedding_function("hashing")
    first = embedding_function(["绿波协调"])[0]
    second = embedding_function(["绿波协调"])[0]

    assert all(left == right for left, right in zip(first, second))
    assert len(first) == 384
    assert math.isclose(sum(value * value for value in first) ** 0.5, 1.0, rel_tol=1e-6)


def test_offline_embedding_ranks_related_text_higher():
    """相关交通文本的向量内积高于无关文本。"""
    embedding_function = get_embedding_function("hashing")
    query, related, unrelated = embedding_function(
        [
            "绿波带是什么",
            "绿波带是干线协调控制中的连续通行时间窗口",
            "道路施工期间需要设置围挡和绕行",
        ]
    )

    related_score = sum(a * b for a, b in zip(query, related))
    unrelated_score = sum(a * b for a, b in zip(query, unrelated))
    assert related_score > unrelated_score


def test_invalid_embedding_backend_raises():
    """未知向量后端给出明确错误。"""
    try:
        get_embedding_function("unknown-backend")
    except ValueError as exc:
        assert "TRAFFIC_EMBEDDING_BACKEND" in str(exc)
    else:
        raise AssertionError("未知向量后端应抛出 ValueError")
