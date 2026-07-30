# Multimodal Hybrid RAG System - Complete Technical Documentation

## 1. Project Overview & Architecture

### What It Is
This project is an **Enterprise-Grade Multimodal Hybrid Retrieval-Augmented Generation (RAG) System**. It allows users to upload complex multimodal documents (PDFs containing formatted text, multi-column tables, diagrams, and images) and ask natural language questions. The system retrieves precise context and generates instant answers using a local, privacy-preserving LLM accelerated on NVIDIA GPUs.

### What We Are Doing
We have built a completely local, self-hosted AI pipeline that replaces cloud APIs (like OpenAI) with local open-source models:
- **Database**: PostgreSQL 16 with the `pgvector` extension for storing high-dimensional vector embeddings and document metadata.
- **Hybrid Retrieval**: Combines **BM25 Keyword Search** (lexical/exact match) and **Dense Vector Search** (semantic/embedding match) using **Reciprocal Rank Fusion (RRF)**.
- **Reranking**: Re-scores top retrieved candidates using a cross-encoder transformer model (`ms-marco-MiniLM-L-6-v2`) to eliminate false positives.
- **Local LLM Generation**: Uses **Mistral-7B-Instruct-v0.2** running in GGUF Q4 format, fully offloaded to the **NVIDIA GeForce RTX 3050 Laptop GPU** via CUDA.
- **Real-Time Streaming UI**: A modern custom web interface serving live Server-Sent Events (SSE) token streams so answers appear word-by-word with instant latency feedback.

### How We Are Doing It (Architecture Diagram)

```
[ User Query in Web UI ]
         │
         ▼
[ FastAPI Server (app/api/server.py) ]
         │
         ├──► 1. Dense Vector Search (app/embeddings/embedder.py + pgvector)
         ├──► 2. Sparse Lexical Search (app/retrieval/bm25_retriever.py)
         │
         ▼
[ Reciprocal Rank Fusion (app/retrieval/hybrid_retriever.py) ]
         │
         ▼
[ Cross-Encoder Reranker (app/retrieval/reranker.py) ]
         │
         ▼
[ GPU-Accelerated Mistral 7B LLM (app/llm/local_llm.py) ]
         │
         ▼
[ Live SSE Token Stream back to static/index.html Web UI ]
```

---

## 2. Concrete Examples

### Example 1: Curriculum Course Query
- **User Question**: *"What is the course code for Information Retrieval and how many credits is it?"*
- **Retrieval Pipeline**:
  1. **BM25 Search**: Matches exact keyword `"CS4674"` and `"Information Retrieval"`.
  2. **Dense Search**: Embeds question semantically to match course listings.
  3. **Reranker**: Selects Chunk #14 containing course details.
- **Context Delivered to LLM**:
  > Source: `B_Tech_AIDS_Curriculum_SNU.pdf` · Page 3: "CS4674 Information Retrieval | Category: Professional Elective | Hours: 3 | Credits: 3"
- **Generated Answer**: *"The course code for Information Retrieval is CS4674. It is categorized as a Professional Elective with 3 credit hours."*
- **Response Time**: `0.85s` (using GPU acceleration).

### Example 2: Multimodal Image/Table Query
- **User Question**: *"What does the architecture diagram on page 2 illustrate?"*
- **Retrieval Pipeline**:
  1. **Dense Vector Search**: Matches extracted image caption embeddings stored during PDF ingestion.
  2. **Reranker**: Ranks the image metadata and neighboring text chunks.
- **Context Delivered to LLM**:
  > Source: `NDD_System.pdf` · Page 2 Image Chunk #2: "Architecture diagram showing MediaPipe landmark tracking fed into OpenCV and Transformer classifiers."
- **Generated Answer**: *"The diagram on page 2 illustrates the system architecture, showing raw video input processed by MediaPipe for facial feature extraction, followed by OpenCV image normalization and classification via a Transformer model."*
- **Response Time**: `1.12s`.

---

## 3. Directory & File Structure

Below is the complete map of the codebase and the exact responsibility of every file:

```
multimodal-rag/
│
├── app/                             # Core Application Package
│   ├── api/                         # FastAPI Web Server & Frontend
│   │   ├── static/
│   │   │   └── index.html           # Modern Glassmorphic Web UI with live SSE token streaming
│   │   └── server.py                # REST & SSE Endpoints (/upload, /ingest, /query/stream)
│   │
│   ├── embeddings/                  # Vector Embedding Generators
│   │   └── embedder.py              # SentenceTransformer model wrapper (nomic-embed-text)
│   │
│   ├── ingestion/                   # Document Parsing & Feature Extraction
│   │   └── pdf_processor.py         # PyMuPDF parser: extracts text, tables, and renders images
│   │
│   ├── llm/                         # Local LLM Inference Engine
│   │   └── local_llm.py             # llama-cpp-python wrapper with CUDA GPU layer offloading
│   │
│   ├── retrieval/                   # Hybrid Retrieval & Reranking Engine
│   │   ├── bm25_retriever.py        # BM25 okapi sparse retriever with dynamic DB cache sync
│   │   ├── hybrid_retriever.py      # Reciprocal Rank Fusion (RRF) combiner
│   │   ├── image_retriever.py       # Image chunk metadata query helper
│   │   └── reranker.py              # Cross-Encoder model (ms-marco-MiniLM-L-6-v2)
│   │
│   ├── ui/                          # Streamlit UI (Legacy backup)
│   │   └── app.py                   # Alternative Streamlit frontend interface
│   │
│   ├── vectorstore/                 # Database Storage Layer
│   │   ├── chroma_store.py          # Vector store abstraction wrapper
│   │   └── pgvector_store.py        # PostgreSQL 16 + pgvector database connector & schema auto-creator
│   │
│   └── config.py                    # Central Configuration (Model paths, ports, DB credentials, GPU settings)
│
├── data/                            # Upload & Storage Directories
│   └── uploads/                     # Storage folder for user-uploaded PDF files
│
├── models/                          # Local Model Binary Storage
│   └── mistral-7b-instruct-v0.2.Q4_K_M.gguf  # Local GGUF LLM weights (4.1 GB)
│
├── main.py                          # CLI Entry Point for batch ingestion & manual query commands
├── requirements.txt                 # Python package dependencies
└── PROJECT_DOCUMENTATION.md         # Technical documentation document
```

---

## 4. End-to-End Execution Pipeline (Step-by-Step)

Here is how data flows through the files in each phase:

### Phase A: Document Ingestion Pipeline
1. **User Uploads File**: User drops a PDF in the Web UI (`app/api/static/index.html`).
2. **File Handler (`app/api/server.py`)**: The `/upload` endpoint saves the file to `data/uploads/`.
3. **Async Subprocess Ingestion**: `/ingest` triggers `main.py ingest <filename>` in a non-blocking background task.
4. **PDF Parsing (`app/ingestion/pdf_processor.py`)**:
   - Uses PyMuPDF (`fitz`) to extract text page-by-page.
   - Chunks text into overlapping windows (~500 chars).
   - Extracts embedded images and stores them as image chunks.
5. **Embedding Generation (`app/embeddings/embedder.py`)**:
   - Generates 768-dimensional dense embeddings for every chunk.
6. **Database Persistence (`app/vectorstore/pgvector_store.py`)**:
   - Ensures `text_chunks` and `image_chunks` tables exist in PostgreSQL.
   - Inserts chunks and vector embeddings into the `pgvector` index.

---

### Phase B: Hybrid Retrieval & Generation Pipeline
1. **User Sends Query**: User types a question on the webpage.
2. **Server Warmup & Handler (`app/api/server.py`)**:
   - On startup, `@app.on_event("startup")` pre-loads the embedding model, reranker, and Mistral LLM into memory.
   - `/query/stream` receives the JSON payload: `{ "question": "...", "mode": "hybrid_rerank", "top_k": 5 }`.
3. **Dense Vector Retrieval (`app/vectorstore/pgvector_store.py`)**:
   - Query is embedded via `embedder.py` and matched using cosine distance in `pgvector`.
4. **Sparse Lexical Retrieval (`app/retrieval/bm25_retriever.py`)**:
   - Checks table count in PostgreSQL. Auto-rebuilds BM25 index if new documents were uploaded.
   - Calculates BM25 score for all document chunks.
5. **Reciprocal Rank Fusion (`app/retrieval/hybrid_retriever.py`)**:
   - Combines Dense and Sparse rank orders using RRF formula: $Score(d) = \sum \frac{w_i}{k + rank_i(d)}$.
6. **Cross-Encoder Reranking (`app/retrieval/reranker.py`)**:
   - Feeds top RRF candidates through `cross-encoder/ms-marco-MiniLM-L-6-v2` to produce accurate relevance scores.
7. **GPU LLM Generation (`app/llm/local_llm.py`)**:
   - Constructs system prompt with top retrieved context passages.
   - Invokes `llama_cpp.Llama` with all 35 layers offloaded to **NVIDIA RTX 3050 GPU**.
   - Streams text tokens live via Server-Sent Events (SSE).
8. **UI Rendering (`app/api/static/index.html`)**:
   - JS `ReadableStream` reads tokens and appends them to the screen live.
   - Appends latency timer badge (`⏱️ Generated in X.XXs`) upon `done` event.

---

## 5. Quick Reference Commands

### Start the GPU Server
```powershell
cd c:\Users\yuvad\Desktop\ideas\multimodal-rag
.\venv\Scripts\Activate.ps1
python -m uvicorn app.api.server:app --port 8000
```

### Access Web Application
Open **`http://localhost:8000`** in your browser.
