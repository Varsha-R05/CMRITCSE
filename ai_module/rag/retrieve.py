
import os
from functools import lru_cache

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "rag", "chroma", "db")


@lru_cache(maxsize=1)
def get_db():
    # Import heavy ML dependencies only when RAG is actually used.
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    return Chroma(
        persist_directory=DB_PATH,
        embedding_function=embeddings,
    )


def retrieve_context(role, company, topic, k=4):
    """Retrieve relevant documents from the existing knowledge base."""

    query = (
        f"Role: {role}\n"
        f"Topic: {topic}\n"
        "Generate interview questions related to this topic."
    )

    db = get_db()
    docs = db.similarity_search(query, k=k)

    context = "\n\n".join(doc.page_content for doc in docs)

    sources = list(dict.fromkeys(
        doc.metadata.get("source", "Unknown")
        for doc in docs
    ))

    return {
        "context": context,
        "sources": sources,
    }
