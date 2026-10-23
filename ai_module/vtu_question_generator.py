import json
import logging
import threading
import time

import numpy as np

from llama.llama_client import ask_llama
from rag.retrieve import db, embeddings


# =========================================================
# VTU INDEX CACHE
# Loads and filters the vector matrix once instead of on
# every request. Results are identical to the uncached version.
# Call reset_vtu_cache() after re-indexing documents.
# =========================================================

_VTU_CACHE = {}
_VTU_LOCK = threading.Lock()


def reset_vtu_cache():
    with _VTU_LOCK:
        _VTU_CACHE.clear()


def _load_vtu_index():
    if _VTU_CACHE:
        return _VTU_CACHE

    with _VTU_LOCK:
        if _VTU_CACHE:
            return _VTU_CACHE

        start_time = time.perf_counter()

        data = db.get(
            include=["documents", "metadatas", "embeddings"]
        )

        documents = data.get("documents") or []
        metadata = data.get("metadatas") or []
        vectors = data.get("embeddings")

        if not documents or vectors is None:
            raise ValueError("ChromaDB contains no indexed documents.")

        vectors = np.asarray(vectors, dtype=np.float32)

        # VTU-only source filtering (unchanged).
        valid_indices = [
            i
            for i, document in enumerate(documents)
            if document
            and i < len(vectors)
            and i < len(metadata)
            and "/KNOWLEDGE_BASE/VTU/"
            in (metadata[i] or {}).get("source", "")
            .replace("\\", "/")
            .upper()
        ]

        if not valid_indices:
            raise ValueError("No VTU documents found in ChromaDB.")

        indices = np.asarray(valid_indices, dtype=np.intp)
        candidate_vectors = vectors[indices]
        vector_norms = np.linalg.norm(candidate_vectors, axis=1)

        valid_norms = vector_norms > 0

        if not np.any(valid_norms):
            raise ValueError("No VTU documents found in ChromaDB.")

        indices = indices[valid_norms]

        _VTU_CACHE["vectors"] = candidate_vectors[valid_norms]
        _VTU_CACHE["norms"] = vector_norms[valid_norms]
        _VTU_CACHE["documents"] = [documents[i] for i in indices]
        _VTU_CACHE["sources"] = [
            (metadata[i] or {}).get("source", "") for i in indices
        ]

        logging.info(
            "VTU index cached (%d chunks) in %.2f seconds",
            len(indices),
            time.perf_counter() - start_time,
        )

        return _VTU_CACHE


def retrieve_vtu_context(subject, module, topic, k=2):
    """Retrieve relevant context only from VTU PDFs."""

    start_time = time.perf_counter()

    query = (
        f"VTU subject: {subject}. "
        f"Module: {module}. Topic: {topic}. "
        "Find academic concepts, definitions, algorithms, "
        "examples, and important questions relevant to this topic."
    )

    index = _load_vtu_index()

    # Generate the query embedding once.
    query_vector = np.asarray(
        embeddings.embed_query(query), dtype=np.float32
    )
    query_norm = np.linalg.norm(query_vector)

    if query_norm == 0:
        raise ValueError("Query embedding has zero magnitude.")

    # Cosine similarity for all candidates at once.
    similarities = (
        index["vectors"] @ query_vector
    ) / (index["norms"] * query_norm)

    # Preserve descending similarity ranking.
    ranked_positions = np.argsort(-similarities, kind="stable")[:k]

    if len(ranked_positions) == 0:
        raise ValueError("No VTU documents found in ChromaDB.")

    context = "\n\n".join(
        index["documents"][position] for position in ranked_positions
    )
    sources = list(
        dict.fromkeys(
            index["sources"][position] for position in ranked_positions
        )
    )

    logging.info(
        "VTU retrieval completed in %.2f seconds",
        time.perf_counter() - start_time,
    )

    return {"context": context, "sources": sources}


# =========================================================
# PROMPT
# Fixed instructions come FIRST so Ollama can reuse its cached
# prompt prefix between questions. Only the part after
# "--- INPUT ---" changes from question to question.
# =========================================================

STATIC_INSTRUCTIONS = """You are an experienced VTU university examiner.

RULES:
1. Use ONLY the retrieved context. Do not invent facts, formulas, syllabus details, or assumptions. The question must be technically correct and supported by the context.
2. Generate exactly ONE clear, focused, single-part examination question. Vary the style to suit the topic and context: theory (definition, explanation, comparison, components, characteristics, advantages, disadvantages), simple programming, basic SQL, problem-solving, basic numericals, or a short application. Do not force programming, SQL, or numericals when the context does not support them. Avoid system design, lengthy coding, and large case studies.
3. Give a concise model answer for evaluating a VTU student: key points for theory, code with a brief note for programming, the query for SQL, essential steps and final answer for numericals. Keep it under 80 words, excluding code.
4. Difficulty is Easy, Medium, or Hard. Prefer Easy or Medium; use Hard only when the context justifies it.

OUTPUT: JSON only, no Markdown, with exactly these fields:
{"question": "One examination question", "expected_answer": "Concise model answer", "difficulty": "Easy, Medium, or Hard"}

--- INPUT ---
"""


def build_vtu_prompt(subject, module, topic, context):
    return (
        f"{STATIC_INSTRUCTIONS}"
        f"Subject: {subject}\n"
        f"Module: {module}\n"
        f"Topic: {topic}\n\n"
        f"Retrieved VTU context:\n{context}\n\n"
        "Return the JSON now."
    )


def generate_vtu_question(subject, module, topic):
    """Generate one VTU question and its expected answer using Llama."""

    retrieved = retrieve_vtu_context(subject, module, topic)

    prompt = build_vtu_prompt(
        subject, module, topic, retrieved["context"]
    )

    raw = ask_llama(
        prompt, max_tokens=800, response_format="json"
    )

    if not raw:
        raise RuntimeError("Llama did not return a question.")

    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as error:
        logging.error("Invalid VTU question JSON: %s", raw)
        raise RuntimeError("Llama returned invalid JSON.") from error

    question = result.get("question")
    expected_answer = result.get("expected_answer")
    difficulty = str(
        result.get("difficulty", "Medium")
    ).capitalize()

    if not isinstance(question, str) or not question.strip():
        raise RuntimeError("Generated question is empty.")

    if (
        not isinstance(expected_answer, str)
        or not expected_answer.strip()
    ):
        raise RuntimeError("Generated expected answer is empty.")

    if difficulty not in {"Easy", "Medium", "Hard"}:
        difficulty = "Medium"

    return {
        "question": question.strip(),
        "expected_answer": expected_answer.strip(),
        "difficulty": difficulty,
        "topic": topic,
        "subject": subject,
        "module": module,
        "sources": retrieved["sources"],
    }