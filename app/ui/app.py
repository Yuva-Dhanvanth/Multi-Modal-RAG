import streamlit as st
import time
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

st.set_page_config(
    page_title="Multimodal RAG",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Sidebar ───────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🔍 Multimodal RAG")
    st.caption("Fully local · GGUF only · No cloud APIs")

    st.divider()

    st.subheader("Retrieval Settings")
    mode = st.selectbox(
        "Retrieval mode",
        options=["hybrid_rerank", "hybrid", "dense", "bm25"],
        index=0,
        help="hybrid_rerank = dense + BM25 + cross-encoder reranker (best quality)",
    )
    top_k = st.slider("Top-K chunks", min_value=1, max_value=10, value=5)

    st.divider()
    st.subheader("📁 Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload PDF, DOCX, TXT, Images",
        type=["pdf", "docx", "txt", "md", "csv", "xlsx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        from app.config import DOCUMENTS_DIR
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)
        saved_count = 0
        for uploaded_file in uploaded_files:
            target_path = os.path.join(DOCUMENTS_DIR, uploaded_file.name)
            with open(target_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            saved_count += 1
        st.success(f"Saved {saved_count} file(s) to data/documents/")
        if st.button("🚀 Ingest Uploaded Files", type="primary", use_container_width=True):
            with st.spinner("Ingesting and embedding documents into PostgreSQL..."):
                from main import run_ingestion
                run_ingestion()
            st.success("Ingestion complete!")
            st.rerun()

    st.divider()
    st.subheader("System")
    if st.button("🔄 Re-ingest existing documents", type="secondary", use_container_width=True):
        with st.spinner("Ingesting..."):
            from main import run_ingestion
            run_ingestion()
        st.success("Ingestion complete!")
        st.rerun()

    st.divider()
    st.subheader("Database Stats")
    try:
        from app.vectorstore import get_collection, get_image_collection
        tc = get_collection().count()
        ic = get_image_collection().count()
        st.metric("Text/Table chunks", tc)
        st.metric("Image chunks", ic)
    except Exception as e:
        st.error(f"DB unavailable: {e}")

    st.divider()
    st.caption("Built for B.Tech AI & DS · SNU Chennai")

# ─── Main panel ────────────────────────────────────────────────────────────

st.title("💬 Ask your documents")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "contexts" in msg:
            with st.expander(f"📄 Retrieved {len(msg['contexts'])} chunks"):
                for i, ctx in enumerate(msg["contexts"]):
                    src = ctx.get("source", "?")
                    pg = ctx.get("page", "?")
                    mod = ctx.get("modality", "text")
                    st.markdown(f"**[{i+1}] {src} · Page {pg} · {mod}**")
                    st.text(ctx.get("text", "")[:500])
            if "images" in msg and msg["images"]:
                st.subheader("🖼️ Retrieved Images")
                for img in msg["images"]:
                    img_path = img.get("image_path", "")
                    cap = img.get("caption", "")
                    if os.path.exists(img_path):
                        st.image(img_path, caption=cap, width=300)
            if "latency" in msg:
                lat = msg["latency"]
                cols = st.columns(3)
                cols[0].metric("Retrieval", f"{lat.get('retrieval_sec', 0):.1f}s")
                cols[1].metric("Generation", f"{lat.get('generation_sec', 0):.1f}s")
                cols[2].metric("Total", f"{lat.get('total_sec', 0):.1f}s")

if prompt := st.chat_input("Ask a question about your documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("⏳ Retrieving context...")

        try:
            t0 = time.time()

            from app.vectorstore.retriever import get_context_for_query
            from app.llm.local_llm import stream_answer
            from app.utils import truncate_contexts
            from app.retrieval.image_retriever import retrieve_images

            if mode == "dense":
                results = get_context_for_query(prompt, mode="dense", top_k=top_k)
                documents = truncate_contexts(results["documents"][0])
                metadatas = results["metadatas"][0][:len(documents)]
            else:
                results = get_context_for_query(prompt, mode=mode, top_k=top_k)
                documents = truncate_contexts(results["documents"], max_chunks=max(top_k, 10))
                metadatas = results["metadatas"][:len(documents)]

            contexts_out = [
                {"text": d[:500], "source": m.get("source", "?"), "page": m.get("page", "?"), "modality": m.get("modality", "?")}
                for d, m in zip(documents, metadatas)
            ]

            t_retrieval = time.time()

            context = "\n\n".join(documents)
            placeholder.empty()
            answer = st.write_stream(stream_answer(context, prompt))

            t_end = time.time()

            n_show = min(top_k, len(contexts_out))
            with st.expander(f"📄 Retrieved {n_show} chunks"):
                for i, ctx in enumerate(contexts_out[:n_show]):
                    st.markdown(f"**[{i+1}] {ctx['source']} · Page {ctx['page']} · {ctx['modality']}**")
                    st.text(ctx["text"][:400])

            if images_out:
                st.subheader("🖼️ Retrieved Images")
                for img in images_out:
                    st.image(img["image_path"], caption=img["caption"], width=300)

            cols = st.columns(3)
            cols[0].metric("Retrieval", f"{latency['retrieval_sec']:.1f}s")
            cols[1].metric("Generation", f"{latency['generation_sec']:.1f}s")
            cols[2].metric("Total", f"{latency['total_sec']:.1f}s")

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "contexts": contexts_out,
                "images": images_out,
                "latency": latency,
            })

        except Exception as e:
            placeholder.error(f"Error: {e}")
