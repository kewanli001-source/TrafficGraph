"""rag_ingest — 将交通专业 Q&A 语料入库到 ChromaDB

所属层：pipelines
依赖：chromadb, python-dotenv
对接算法层：N/A（本地向量检索）
"""
import json
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from src.knowledge import get_embedding_function

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
JSONL_PATH = PROJECT_ROOT / "data" / "traffic_qa_corpus.jsonl"
DB_PATH = str(PROJECT_ROOT / "data" / "traffic_knowledge")
COLLECTION_NAME = "traffic_qa"
BATCH_SIZE = 100


def _clean_think(text: str) -> str:
    """移除语料中的思考标签，仅保留最终回答。"""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _classify_system(system: str) -> str:
    """根据系统提示词识别语料类别。"""
    if any(keyword in system for keyword in ("规范", "标准", "GB 14886", "道路交通标志")):
        return "standard"
    if any(keyword in system for keyword in ("信号", "配时", "绿波", "Webster", "相位")):
        return "signal"
    if any(keyword in system for keyword in ("事件", "事故", "施工", "抛锚", "管制")):
        return "incident"
    if any(keyword in system for keyword in ("调度", "警力", "派单", "救援", "拖车")):
        return "dispatch"
    if any(keyword in system for keyword in ("流量", "速度", "拥堵", "排队", "饱和")):
        return "flow"
    return "general"


def _load_rows(jsonl_path: Path) -> list[tuple[str, str, str]]:
    """读取并校验 Q&A JSONL。

    Args:
        jsonl_path: 语料路径。

    Returns:
        [(system, question, answer), ...]

    Raises:
        FileNotFoundError: 语料文件不存在。
        ValueError: 语料中没有有效条目。
    """
    if not jsonl_path.exists():
        raise FileNotFoundError(f"语料文件不存在: {jsonl_path}")

    rows: list[tuple[str, str, str]] = []
    with open(jsonl_path, encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                messages = payload["messages"]
                system = str(messages[0]["content"]).strip()
                question = str(messages[1]["content"]).strip()
                answer = _clean_think(str(messages[2]["content"]))
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                raise ValueError(f"语料第 {line_number} 行格式非法: {exc}") from exc
            if question and answer:
                rows.append((system, question, answer))

    if not rows:
        raise ValueError(f"语料没有有效条目: {jsonl_path}")
    return rows


def ingest(
    jsonl_path: str = str(JSONL_PATH),
    db_path: str = DB_PATH,
    rebuild: bool = False,
) -> int:
    """将交通 Q&A 语料入库到 ChromaDB。

    Args:
        jsonl_path: 交通语料 JSONL 文件路径。
        db_path: ChromaDB 持久化目录。
        rebuild: 为 True 时删除已有集合并全量重建。

    Returns:
        入库条目总数。

    Raises:
        FileNotFoundError: 语料文件不存在。
        ValueError: 语料格式非法。
        ImportError: chromadb 或 embedding 依赖未安装。
    """
    import chromadb

    rows = _load_rows(Path(jsonl_path))
    embedding_function = get_embedding_function()
    client = chromadb.PersistentClient(path=db_path)

    existing = [collection.name for collection in client.list_collections()]
    if COLLECTION_NAME in existing:
        collection = client.get_collection(
            COLLECTION_NAME,
            embedding_function=embedding_function,
        )
        if collection.count() > 0 and not rebuild:
            count = collection.count()
            print(f"[rag_ingest] 已存在 {count} 条，跳过入库。使用 --rebuild 可重建。")
            return count
        client.delete_collection(COLLECTION_NAME)

    collection = client.create_collection(
        COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"},
    )

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    for index, (system, question, answer) in enumerate(rows):
        documents.append(f"问题：{question}\n回答：{answer}")
        metadatas.append(
            {
                "system_type": _classify_system(system),
                "system": system[:200],
                "source": question[:80],
            }
        )
        ids.append(f"traffic_{index}")

        if len(documents) >= BATCH_SIZE:
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            print(f"  已入库 {index + 1} 条...", end="\r")
            documents, metadatas, ids = [], [], []

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)

    total = collection.count()
    print(f"\n[rag_ingest] 入库完成，共 {total} 条。")
    return total


def append_supplement(
    supplement_path: Optional[str] = None,
    db_path: str = DB_PATH,
) -> int:
    """将补充交通语料追加到现有集合。

    Args:
        supplement_path: 补充语料路径，默认 data/traffic_qa_supplement.jsonl。
        db_path: ChromaDB 持久化目录。

    Returns:
        新增条目数。

    Raises:
        FileNotFoundError: 补充语料或目标集合不存在。
        ValueError: 语料格式非法。
    """
    import chromadb

    source = Path(supplement_path) if supplement_path else PROJECT_ROOT / "data" / "traffic_qa_supplement.jsonl"
    rows = _load_rows(source)

    embedding_function = get_embedding_function()
    client = chromadb.PersistentClient(path=db_path)
    existing = [collection.name for collection in client.list_collections()]
    if COLLECTION_NAME not in existing:
        raise FileNotFoundError(
            f"交通知识库尚未初始化，请先运行 python -m src.pipelines.rag_ingest"
        )
    collection = client.get_collection(
        COLLECTION_NAME,
        embedding_function=embedding_function,
    )
    existing_count = collection.count()

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    for index, (system, question, answer) in enumerate(rows):
        documents.append(f"问题：{question}\n回答：{answer}")
        metadatas.append(
            {
                "system_type": _classify_system(system),
                "system": system[:200],
                "source": question[:80],
            }
        )
        ids.append(f"traffic_supplement_{existing_count + index}")

    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    new_total = collection.count()
    print(
        f"[rag_ingest] 补充入库完成：新增 {len(rows)} 条，"
        f"集合从 {existing_count} → {new_total} 条"
    )
    return len(rows)


if __name__ == "__main__":
    import sys

    rebuild_flag = "--rebuild" in sys.argv
    if "--append" in sys.argv:
        append_supplement()
    else:
        ingest(rebuild=rebuild_flag)
