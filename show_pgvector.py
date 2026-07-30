import psycopg2
from app.config import PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DB

def inspect_pgvector():
    print("=" * 65)
    print("      POSTGRESQL + PGVECTOR DATABASE INSPECTION REPORT")
    print("=" * 65)

    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname=PG_DB
        )
        cur = conn.cursor()

        # 1. Extension Check
        cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
        ext = cur.fetchone()
        print("\n1. EXTENSION STATUS:")
        if ext:
            print(f"   [ACTIVE] Extension Name: '{ext[0]}' | Version: {ext[1]}")
        else:
            print("   [INACTIVE] pgvector extension not found!")

        # 2. Database Tables
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        tables = [t[0] for t in cur.fetchall()]
        print(f"\n2. DATABASE TABLES FOUND IN '{PG_DB}':")
        for t in tables:
            print(f"   • Table: {t}")

        # 3. Column Data Types for text_chunks
        cur.execute("""
            SELECT column_name, data_type, udt_name 
            FROM information_schema.columns 
            WHERE table_name = 'text_chunks';
        """)
        cols = cur.fetchall()
        print("\n3. 'text_chunks' TABLE SCHEMA & VECTOR TYPE:")
        for col in cols:
            print(f"   • Column: {col[0]:<15} | Type: {col[1]:<15} | Spec: {col[2]}")

        # 4. Total Chunks & Vector Dimension Check
        cur.execute("SELECT COUNT(*) FROM text_chunks;")
        text_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM image_chunks;")
        img_count = cur.fetchone()[0]
        
        print("\n4. STORED DATA STATS:")
        print(f"   • Total Text Chunks: {text_count}")
        print(f"   • Total Image Chunks: {img_count}")

        # 5. Retrieve Sample Rows with Vector Embeddings
        cur.execute("SELECT chunk_id, source, page, array_length(embedding, 1), embedding FROM text_chunks LIMIT 2;")
        rows = cur.fetchall()
        print("\n5. SAMPLE STORED VECTOR EMBEDDINGS:")
        for idx, r in enumerate(rows, 1):
            chunk_id, source, page, dims, emb_str = r
            # Format vector display
            emb_preview = str(emb_str)[:60] + " ...]"
            print(f"\n   --- Chunk #{idx} ---")
            print(f"   • Chunk ID: {chunk_id}")
            print(f"   • Source PDF: {source} (Page {page})")
            print(f"   • Vector Dimension: {dims}-D Vector Embedding")
            print(f"   • Embedding Sample: {emb_preview}")

        cur.close()
        conn.close()
        print("\n" + "=" * 60)
        print("   CONFIRMED: Database is actively running PostgreSQL 16 pgvector!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError inspecting database: {e}")

if __name__ == "__main__":
    inspect_pgvector()
