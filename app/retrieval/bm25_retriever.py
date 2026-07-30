import re
from rank_bm25 import BM25Okapi

from app.config import BM25_B, BM25_K1, TOP_K_BM25

_corpus_texts = None
_corpus_ids = None
_corpus_metadatas = None
_bm25 = None


def _tokenize(text):
    return re.findall(r"\w+", text.lower())


_last_count = -1


def load_corpus_from_chromadb():
    global _corpus_texts, _corpus_ids, _corpus_metadatas, _bm25, _last_count

    from app.vectorstore import get_collection

    collection = get_collection()
    try:
        current_count = collection.count()
    except Exception:
        current_count = 0

    if _bm25 is not None and current_count == _last_count:
        return

    all_data = collection.get(include=["documents", "metadatas"])
    _corpus_texts = all_data["documents"]
    _corpus_ids = all_data["ids"]
    _corpus_metadatas = all_data["metadatas"]

    tokenized = [_tokenize(doc) for doc in _corpus_texts]
    _bm25 = BM25Okapi(tokenized, k1=BM25_K1, b=BM25_B)
    _last_count = current_count
    print(f"BM25 index built over {len(_corpus_texts)} chunks.")


def retrieve(query, top_k=TOP_K_BM25):
    load_corpus_from_chromadb()
    if _bm25 is None or not _corpus_texts:
        return {
            "documents": [],
            "metadatas": [],
            "ids": [],
            "scores": [],
            "distances": [],
        }
    tokenized_query = _tokenize(query)
    scores = _bm25.get_scores(tokenized_query)
    top_indices = sorted(
        range(len(scores)), key=lambda i: scores[i], reverse=True
    )[:top_k]

    results = {
        "documents": [],
        "metadatas": [],
        "ids": [],
        "scores": [],
        "distances": [],
    }
    for idx in top_indices:
        results["documents"].append(_corpus_texts[idx])
        results["metadatas"].append(_corpus_metadatas[idx])
        results["ids"].append(_corpus_ids[idx])
        results["scores"].append(float(scores[idx]))
        results["distances"].append(1.0 / (1.0 + float(scores[idx])))
    return results
