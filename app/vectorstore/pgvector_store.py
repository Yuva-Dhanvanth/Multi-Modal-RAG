"""
PGVector store — stores embeddings in PostgreSQL as FLOAT[] arrays.
Computes cosine similarity in Python (no native pgvector extension needed).
"""

import os
import psycopg2
import psycopg2.extras
import numpy as np
from app.config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD, TOP_K


def _get_conn():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS text_chunks (
            id SERIAL PRIMARY KEY,
            chunk_id TEXT UNIQUE,
            document TEXT,
            page INT,
            source TEXT,
            format TEXT,
            modality TEXT,
            embedding FLOAT8[]
        );
        CREATE TABLE IF NOT EXISTS image_chunks (
            id SERIAL PRIMARY KEY,
            image_id TEXT UNIQUE,
            caption TEXT,
            source TEXT,
            page INT,
            format TEXT,
            modality TEXT,
            image_path TEXT,
            width INT,
            height INT,
            embedding FLOAT8[]
        );
        """)
    conn.commit()
    return conn


def _cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _array_to_pgarray(arr):
    """Convert a Python list to PostgreSQL array literal."""
    return "{" + ",".join(str(x) for x in arr) + "}"


class PGVectorStore:
    """Drop-in replacement for ChromaDB store using PostgreSQL."""

    @staticmethod
    def get_collection():
        """Compatibility: returns self for API parity with chroma_store."""
        return PGVectorStore()

    @staticmethod
    def get_image_collection():
        return PGVectorStore(image=True)

    def __init__(self, image=False):
        self.image = image
        self.table = "image_chunks" if image else "text_chunks"
        self.id_col = "image_id" if image else "chunk_id"
        self.doc_col = "caption" if image else "document"

    def count(self):
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {self.table}")
            return cur.fetchone()[0]
        finally:
            conn.close()

    def add(self, ids, documents, embeddings=None, metadatas=None):
        """Add documents with embeddings and metadata."""
        conn = _get_conn()
        try:
            cur = conn.cursor()
            for i, doc_id in enumerate(ids):
                doc = documents[i] if documents else ""
                emb = embeddings[i] if embeddings else None
                meta = metadatas[i] if metadatas else {}

                if self.image:
                    cur.execute(
                        f"""INSERT INTO {self.table}
                            ({self.id_col}, caption, source, page, format, modality, image_path, width, height, embedding)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT ({self.id_col}) DO UPDATE SET
                                caption=EXCLUDED.caption, embedding=EXCLUDED.embedding""",
                        (
                            doc_id,
                            doc,
                            meta.get("source", ""),
                            meta.get("page", 1),
                            meta.get("format", ""),
                            meta.get("modality", "image"),
                            meta.get("image_path", ""),
                            meta.get("width", 0),
                            meta.get("height", 0),
                            _array_to_pgarray(emb) if emb else None,
                        ),
                    )
                else:
                    cur.execute(
                        f"""INSERT INTO {self.table}
                            ({self.id_col}, document, page, source, format, modality, embedding)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT ({self.id_col}) DO UPDATE SET
                                document=EXCLUDED.document, embedding=EXCLUDED.embedding""",
                        (
                            doc_id,
                            doc,
                            meta.get("page", 1),
                            meta.get("source", ""),
                            meta.get("format", ""),
                            meta.get("modality", "text"),
                            _array_to_pgarray(emb) if emb else None,
                        ),
                    )
            conn.commit()
            print(f"Stored {len(ids)} chunks in PostgreSQL ({self.table})")
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def query(self, query_embeddings, n_results=TOP_K):
        """
        Query by embedding vector.
        Returns dict with keys: ids, documents, metadatas, distances (list of lists).
        """
        qe = query_embeddings[0]  # single query
        conn = _get_conn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(f"SELECT * FROM {self.table}")
            rows = cur.fetchall()

            scored = []
            for row in rows:
                db_emb = row["embedding"]
                if db_emb is None:
                    continue
                sim = _cosine_similarity(qe, db_emb)
                scored.append((sim, row))

            scored.sort(key=lambda x: x[0], reverse=True)
            top = scored[:n_results]

            ids = [[str(r["id"]) for _, r in top]]
            documents = [[r[self.doc_col] for _, r in top]]
            metadatas = [
                [
                    {
                        "source": r.get("source", ""),
                        "page": r.get("page", 1),
                        "format": r.get("format", ""),
                        "modality": r.get("modality", "text"),
                        "image_path": r.get("image_path", ""),
                        "width": r.get("width", 0),
                        "height": r.get("height", 0),
                    }
                    for _, r in top
                ]
            ]
            distances = [[1.0 - s for s, _ in top]]

            return {"ids": ids, "documents": documents, "metadatas": metadatas, "distances": distances}
        finally:
            conn.close()

    def get(self, include=None, limit=None):
        """Get all documents (for BM25 index building)."""
        conn = _get_conn()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            query = f"SELECT * FROM {self.table}"
            if limit:
                query += f" LIMIT {limit}"
            cur.execute(query)
            rows = cur.fetchall()

            result = {
                "ids": [str(r["id"]) for r in rows],
                "documents": [r[self.doc_col] for r in rows],
                "metadatas": [
                    {
                        "source": r.get("source", ""),
                        "page": r.get("page", 1),
                        "format": r.get("format", ""),
                        "modality": r.get("modality", "text"),
                        "image_path": r.get("image_path", ""),
                    }
                    for r in rows
                ],
            }
            return result
        finally:
            conn.close()


def get_collection():
    return PGVectorStore().get_collection()


def get_image_collection():
    return PGVectorStore(image=True).get_image_collection()


def store_chunks(chunks, embeddings):
    store = PGVectorStore()
    ids = [str(c["chunk_id"]) for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "page": c["page"],
            "source": c["source"],
            "format": c.get("format", "unknown"),
            "modality": c.get("modality", "text"),
        }
        for c in chunks
    ]
    store.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)


def store_image_chunks(image_chunks):
    store = PGVectorStore(image=True)
    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for i, img in enumerate(image_chunks):
        caption = img.get("caption", "")
        doc_text = caption if caption else f"Image from {img['source']} page {img.get('page','?')}"
        ids.append(f"img_{i}")
        documents.append(doc_text)
        metadatas.append(
            {
                "source": img["source"],
                "page": img.get("page", 1),
                "format": img.get("format", "unknown"),
                "modality": "image",
                "image_path": img["image_path"],
                "width": img.get("width", 0),
                "height": img.get("height", 0),
            }
        )
        if img.get("text_embedding") is not None:
            embeddings.append(img["text_embedding"])

    store.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
