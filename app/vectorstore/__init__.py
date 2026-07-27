"""PGVector store — PostgreSQL-backed vector database."""

from app.vectorstore.pgvector_store import (
    get_collection,
    get_image_collection,
    store_chunks,
    store_image_chunks,
    PGVectorStore,
)


def clear_collections():
    import psycopg2
    from app.config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)
    cur = conn.cursor()
    cur.execute("DELETE FROM text_chunks; DELETE FROM image_chunks;")
    conn.commit()
    conn.close()
    print("Cleared PostgreSQL collections")
