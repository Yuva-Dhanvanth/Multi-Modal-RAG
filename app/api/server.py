import os
import sys

if sys.platform == "win32":
    cuda_path = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin"
    if os.path.exists(cuda_path):
        try:
            os.add_dll_directory(cuda_path)
        except Exception:
            pass

import time
from typing import List, Optional
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

app = FastAPI(title="Multimodal RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    print("[INIT] Pre-loading AI models (Embeddings, Reranker, Mistral LLM) on server startup...")
    from app.embeddings.embedder import embed_text
    from app.retrieval.reranker import Reranker
    from app.llm.local_llm import get_llm

    Reranker.get_instance()
    get_llm()
    print("[INIT] ALL MODELS LOADED & READY FOR INSTANT QUERIES!")


class QueryRequest(BaseModel):
    question: str
    mode: str = "hybrid_rerank"
    top_k: int = 5


class QueryResponse(BaseModel):
    question: str
    answer: str
    mode: str
    contexts: list
    latencies: dict


class IngestResponse(BaseModel):
    status: str
    message: str


# Lazy-loaded references
_embedder = None
_llm = None
_retriever = None


def _get_models():
    global _embedder, _llm, _retriever
    if _embedder is None:
        from app.embeddings.embedder import embed_text
        _embedder = embed_text
    if _llm is None:
        from app.llm.local_llm import generate_answer
        _llm = generate_answer
    if _retriever is None:
        from app.vectorstore.retriever import get_context_for_query
        _retriever = get_context_for_query
    return _embedder, _llm, _retriever


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    static_html = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_html):
        with open(static_html, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Multimodal RAG API Running</h1>"


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    from app.utils import truncate_contexts

    _, generate_answer_fn, retrieve_fn = _get_models()

    t0 = time.time()

    if request.mode == "dense":
        results = retrieve_fn(request.question, mode="dense", top_k=request.top_k)
        documents = truncate_contexts(results["documents"][0])
        metadatas = results["metadatas"][0][: len(documents)]
    else:
        results = retrieve_fn(request.question, mode=request.mode, top_k=request.top_k)
        documents = truncate_contexts(results["documents"])
        metadatas = results["metadatas"][: len(documents)]

    t_retrieval = time.time()
    context = "\n\n".join(documents)
    answer = generate_answer_fn(context, request.question)

    t_end = time.time()

    contexts_out = [
        {
            "text": doc[:300],
            "source": meta.get("source", "?"),
            "page": meta.get("page", "?"),
            "modality": meta.get("modality", "text"),
        }
        for doc, meta in zip(documents, metadatas)
    ]

    return QueryResponse(
        question=request.question,
        answer=answer,
        mode=request.mode,
        contexts=contexts_out,
        latencies={
            "retrieval_sec": round(t_retrieval - t0, 2),
            "generation_sec": round(t_end - t_retrieval, 2),
            "total_sec": round(t_end - t0, 2),
        },
    )


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    from app.utils import truncate_contexts
    from app.llm.local_llm import stream_answer
    import json

    _, _, retrieve_fn = _get_models()

    async def event_generator():
        t0 = time.time()
        yield {"event": "status", "data": "retrieving"}

        if request.mode == "dense":
            results = retrieve_fn(request.question, mode="dense", top_k=request.top_k)
            documents = truncate_contexts(results["documents"][0])
            metadatas = results["metadatas"][0][: len(documents)]
        else:
            results = retrieve_fn(request.question, mode=request.mode, top_k=request.top_k)
            documents = truncate_contexts(results["documents"])
            metadatas = results["metadatas"][: len(documents)]

        contexts_out = [
            {
                "text": doc[:300],
                "source": meta.get("source", "?"),
                "page": meta.get("page", "?"),
                "modality": meta.get("modality", "text"),
            }
            for doc, meta in zip(documents, metadatas)
        ]

        yield {
            "event": "contexts",
            "data": json.dumps(contexts_out),
        }

        yield {"event": "status", "data": "generating"}

        context = "\n\n".join(documents)
        for token in stream_answer(context, request.question):
            yield {
                "event": "token",
                "data": token,
            }

        t_end = time.time()
        yield {
            "event": "done",
            "data": json.dumps({
                "latency_sec": round(t_end - t0, 2)
            })
        }

    from sse_starlette.sse import EventSourceResponse
    return EventSourceResponse(event_generator())


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    from app.config import DOCUMENTS_DIR

    os.makedirs(DOCUMENTS_DIR, exist_ok=True)
    saved_files = []
    for file in files:
        file_path = os.path.join(DOCUMENTS_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        saved_files.append(file.filename)

    return {"status": "success", "saved_files": saved_files}


@app.post("/ingest", response_model=IngestResponse)
async def run_ingestion_endpoint():
    import asyncio
    import sys

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "main.py", "ingest",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            return IngestResponse(status="success", message="Ingestion completed.")
        else:
            err_msg = stderr.decode(errors="ignore")[-500:]
            return IngestResponse(
                status="error", message=err_msg
            )
    except Exception as e:
        return IngestResponse(status="error", message=str(e))
