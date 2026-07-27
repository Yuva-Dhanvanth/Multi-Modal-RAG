"""Launch the Multimodal RAG Streamlit UI."""
import os
import sys

if __name__ == "__main__":
    os.system("streamlit run app/ui/app.py --server.port 8501")
