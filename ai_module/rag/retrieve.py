import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "rag", "chroma", "db")

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

db = Chroma(
    persist_directory=DB_PATH,
    embedding_function=embeddings
)


def retrieve_context(role, company, topic, k=4):
    """
    Retrieve the most relevant documents from the knowledge base.
    """

    query = f"""
Role: {role}
Topic: {topic}

Generate interview questions related to this topic.
"""

    docs = db.similarity_search(query, k=k)

    context = "\n\n".join(
        doc.page_content
        for doc in docs
    )

    sources = list(
        dict.fromkeys(
            doc.metadata.get("source", "Unknown")
            for doc in docs
        )
    )

    return {
        "context": context,
        "sources": sources
    }