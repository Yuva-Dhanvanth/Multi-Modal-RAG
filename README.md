# Multimodal RAG System (Fully Local)

A fully offline, local Multimodal Retrieval-Augmented Generation (RAG) system built with Python, PostgreSQL (pgvector), llama-cpp-python (Mistral-7B GGUF), SentenceTransformers, and BM25 hybrid retrieval.

---

## 🏗️ Architecture

- **LLM Runtime**: `llama-cpp-python` with `Mistral-7B-Instruct-v0.2.Q4_K_M.gguf`
- **Embedding Model**: `nomic-ai/nomic-embed-text-v1.5` (768-dim)
- **Vector Storage**: PostgreSQL + `pgvector` extension
- **Sparse Retrieval**: BM25 (`rank-bm25`)
- **Hybrid Fusion**: Reciprocal Rank Fusion (RRF with weights Dense=0.6, BM25=0.4)
- **Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Document Parsing**: PyMuPDF (`fitz`), `python-docx`, `pandas`, `pillow`
- **Interfaces**: CLI (`main.py`), Streamlit UI (`run_ui.py`), REST API (`app/api/server.py`)
- **Evaluation**: RAGAS (Offline mode with local LLM judge)

---

## 🚀 Quick Start Guide

### 1. Requirements & Prerequisites
- Python 3.10+
- PostgreSQL 16+ with `pgvector` extension enabled
- Mistral 7B GGUF model (`models/mistral-7b-instruct-v0.2.Q4_K_M.gguf`)

### 2. Environment Setup
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Ensure dependencies are installed
pip install -r requirements.txt
```

### 3. Ingestion
Place your documents (PDF, DOCX, TXT, images) inside `data/documents/` and run:
```powershell
python main.py ingest
```

### 4. Querying via CLI
```powershell
# Interactive mode
python main.py query

# Single question
python main.py query "What is the course code for Artificial Intelligence?" --mode hybrid_rerank
```

### 5. Streamlit Web UI
```powershell
python run_ui.py
# Opens at http://localhost:8501
```

### 6. REST API Server
```powershell
python -m uvicorn app.api.server:app --reload --port 8000
# OpenAPI Docs: http://localhost:8000/docs
```

### 7. Evaluation & Ablation Study
```powershell
# Run evaluation on sample dataset
python main.py evaluate --sample 5

# Run full ablation study (Dense vs BM25 vs Hybrid vs Hybrid+Rerank)
python main.py ablation --sample 5
```
