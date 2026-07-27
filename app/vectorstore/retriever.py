from app.config import TOP_K, TOP_K_DENSE, TOP_K_BM25, TOP_K_HYBRID, TOP_K_RERANK
from app.vectorstore import get_collection


def get_context_for_query(query, mode="hybrid", top_k=None):
    if mode == "dense":
        return _dense_retrieve(query, top_k=top_k)
    elif mode == "bm25":
        return _bm25_retrieve(query, top_k=top_k)
    elif mode == "hybrid":
        return _hybrid_retrieve(query, top_k=top_k)
    elif mode == "hybrid_rerank":
        return _hybrid_rerank_retrieve(query, top_k=top_k)
    else:
        return _dense_retrieve(query, top_k=top_k)


def _dense_retrieve(query, top_k=None):
    from app.embeddings.embedder import embed_text

    k = top_k or TOP_K_DENSE
    collection = get_collection()
    query_embedding = embed_text(query, is_query=True).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=k)
    return results


def _bm25_retrieve(query, top_k=None):
    from app.retrieval.bm25_retriever import retrieve as bm25_retrieve_fn

    return bm25_retrieve_fn(query, top_k=top_k or TOP_K_BM25)


def _hybrid_retrieve(query, top_k=None):
    from app.retrieval.hybrid_retriever import retrieve as hybrid_retrieve_fn

    return hybrid_retrieve_fn(query, top_k=top_k or TOP_K_HYBRID)


def _hybrid_rerank_retrieve(query, top_k=None):
    from app.retrieval.hybrid_retriever import retrieve_with_rerank

    k = top_k or TOP_K_HYBRID
    return retrieve_with_rerank(query, top_k=k, rerank_top_k=TOP_K_RERANK)


def retrieve(query, top_k=TOP_K):
    from app.embeddings.embedder import embed_text
    collection = get_collection()
    query_embedding = embed_text(query, is_query=True).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
    return results
