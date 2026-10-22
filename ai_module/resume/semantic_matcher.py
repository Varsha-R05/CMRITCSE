
from sentence_transformers import SentenceTransformer, util

_embedding_model = None


def get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            "all-MiniLM-L6-v2",
            device="cpu"
        )

    return _embedding_model


SKILL_ALIASES = {
    "node.js": [
        "node",
        "express",
        "javascript runtime",
        "backend js",
        "express.js"
    ],
    "react": [
        "reactjs",
        "react.js",
        "frontend library",
        "ui framework"
    ],
    "python": [
        "py",
        "django",
        "flask",
        "fastapi",
        "pandas",
        "numpy"
    ],
    "database": [
        "sql",
        "mongodb",
        "postgresql",
        "mysql",
        "nosql",
        "dbms",
        "rdbms"
    ],
    "cloud": [
        "aws",
        "azure",
        "gcp",
        "docker",
        "kubernetes",
        "ci/cd",
        "devops"
    ]
}


ROLE_CORE_REQUIREMENTS = {
    "backend engineer": [
        "python", "node.js", "database", "sql", "postgresql",
        "docker", "aws", "microservices", "rest apis", "redis"
    ],
    "frontend developer": [
        "react", "javascript", "typescript", "html", "css",
        "ui framework", "redux", "tailwind", "responsive design",
        "graphql"
    ],
    "full stack developer": [
        "react", "node.js", "python", "database", "sql",
        "docker", "aws", "rest apis", "git", "ci/cd"
    ],
    "data scientist": [
        "python", "pandas", "numpy", "machine learning", "sql",
        "statistics", "tensorflow", "pytorch", "data analysis",
        "scikit-learn"
    ],
    "devops engineer": [
        "cloud", "aws", "docker", "kubernetes", "ci/cd",
        "terraform", "linux", "jenkins", "monitoring", "automation"
    ],
    "software engineer": [
        "python", "javascript", "database", "sql", "git",
        "problem solving", "data structures", "algorithms",
        "rest apis", "testing"
    ]
}


def expand_aliases(text: str) -> str:
    text_lower = text.lower()
    expanded_terms = [text_lower]

    for canonical, aliases in SKILL_ALIASES.items():
        if any(alias in text_lower for alias in aliases):
            expanded_terms.append(canonical)

    return " ".join(expanded_terms)


def resolve_target_description(role: str, jd_text: str) -> str:
    """Build a target description from the role and optional job description."""

    role_clean = role.strip().lower() if role else "software engineer"
    jd_clean = jd_text.strip() if jd_text else ""

    matched_role_skills = []

    for known_role, skills in ROLE_CORE_REQUIREMENTS.items():
        if known_role in role_clean:
            matched_role_skills = skills
            break

    if not matched_role_skills:
        matched_role_skills = ROLE_CORE_REQUIREMENTS["software engineer"]

    role_synthetic_context = (
        f"Target Role: {role_clean}. "
        f"Key technical requirements include: "
        f"{', '.join(matched_role_skills)}."
    )

    if jd_clean:
        return (
            f"{role_synthetic_context} "
            f"Detailed Job Description: {jd_clean}"
        )

    return role_synthetic_context


def calculate_rag_semantic_match(
    resume_text: str,
    role: str,
    jd_text: str = ""
) -> float:
    """Calculate semantic similarity between a resume and target role."""

    embedding_model = get_embedding_model()

    target_context = resolve_target_description(role, jd_text)

    expanded_resume = expand_aliases(resume_text)
    expanded_target = expand_aliases(target_context)

    resume_emb = embedding_model.encode(
        expanded_resume,
        convert_to_tensor=False
    )

    target_emb = embedding_model.encode(
        expanded_target,
        convert_to_tensor=False
    )

    similarity = util.cos_sim(
        resume_emb,
        target_emb
    ).item()

    return round(
        max(0.0, min(100.0, similarity * 100)),
        2
    )
