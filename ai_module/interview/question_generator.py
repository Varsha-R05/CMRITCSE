
import json
import random
import re
import time
from difflib import SequenceMatcher

from llama.llama_client import ask_llama
from rag.retrieve import retrieve_context
from interview.company_profiles import COMPANY_STYLE
from interview.interview_engine import adjust_difficulty


STOPWORDS = {
    "a", "an", "the", "is", "are", "of", "in", "on", "to", "for",
    "and", "or", "what", "how", "why", "does", "do", "can", "you",
    "explain", "between", "difference", "primary", "main", "goal",
    "purpose", "with", "that", "this", "it", "its", "by", "as",
    "be", "when", "which", "would", "could", "should", "your",
    "their", "using", "use", "describe", "tell", "me", "about",
}

MAX_ATTEMPTS = 3
NUM_PREDICT = 500


# =========================================================
# ROLE-SPECIFIC SKILL SIGNALS
# =========================================================

ROLE_SKILLS = {
    "software developer": [
        "programming", "algorithm", "data structure", "array",
        "string", "linked list", "stack", "queue", "tree", "graph",
        "hash table", "hashmap", "dictionary", "sorting", "searching",
        "time complexity", "space complexity", "big o", "recursion",
        "object oriented", "oop", "class", "object", "inheritance",
        "polymorphism", "encapsulation", "abstraction", "debugging",
        "function", "variable", "loop", "exception", "unit testing",
        "software testing", "sql", "database", "api", "http",
        "operating system", "memory", "concurrency", "git",
        "version control", "compiler", "code",
    ],
    "python developer": [
        "python", "list", "tuple", "dictionary", "set", "string",
        "function", "class", "object", "inheritance", "decorator",
        "generator", "iterator", "exception", "module", "package",
        "list comprehension", "file handling", "lambda", "pip",
        "virtual environment", "debugging", "algorithm", "data structure",
        "api", "testing",
    ],
    "full stack developer": [
        "html", "css", "javascript", "frontend", "backend", "react",
        "angular", "vue", "node", "api", "rest", "http", "database",
        "sql", "authentication", "authorization", "server", "client",
        "web application", "responsive", "debugging", "testing",
    ],
    "backend developer": [
        "api", "rest", "http", "database", "sql", "server",
        "authentication", "authorization", "caching", "concurrency",
        "data structure", "algorithm", "exception", "testing",
        "networking", "performance",
    ],
    "frontend developer": [
        "html", "css", "javascript", "typescript", "react", "angular",
        "vue", "dom", "browser", "responsive", "accessibility",
        "component", "state", "event", "api", "frontend", "web",
    ],
    "data scientist": [
        "statistics", "probability", "python", "pandas", "numpy",
        "data cleaning", "data analysis", "regression", "classification",
        "machine learning", "model evaluation", "feature engineering",
        "visualization", "overfitting", "underfitting",
    ],
    "machine learning engineer": [
        "machine learning", "model", "training", "inference",
        "feature engineering", "overfitting", "underfitting",
        "classification", "regression", "evaluation", "python",
        "neural network", "deployment", "data pipeline",
    ],
}


LOW_PRIORITY_GENERAL_TOPICS = [
    "waterfall model",
    "incremental model",
    "software development life cycle",
    "software development lifecycle",
    "project management methodology",
    "agile methodology",
    "scrum methodology",
    "requirements engineer",
    "requirements engineering",
]


DIFFICULTY_GUIDE = {
    "Easy": (
        "Ask for a simple definition or a basic example of the concept."
    ),
    "Medium": (
        "Ask for a comparison, a use case, or how the concept works "
        "in a small scenario."
    ),
    "Hard": (
        "Ask about a trade-off, an edge case, or what goes wrong in a "
        "short scenario. Still entry-level, no system design."
    ),
}


# =========================================================
# FOCUS CONCEPTS
# =========================================================

OOP_FOCUS = [
    "encapsulation with a simple class example",
    "inheritance and method reuse",
    "method overloading vs method overriding",
    "abstract class vs interface",
    "polymorphism with a practical example",
    "constructors and object initialization",
    "composition vs inheritance",
    "access modifiers (public, private, protected)",
    "static vs instance members",
    "the this / self reference",
    "class vs object",
    "abstraction and hiding implementation details",
]


TOPIC_SUBTOPICS = {
    "object oriented programming": OOP_FOCUS,
    "oops": OOP_FOCUS,
    "oop": OOP_FOCUS,
    "dsa": [
        "array vs linked list",
        "stack use cases",
        "queue vs stack",
        "hash map collisions",
        "binary search time complexity",
        "reversing a string",
        "detecting duplicates in an array",
        "BFS vs DFS",
        "bubble sort vs merge sort",
        "Big O of nested loops",
    ],
    "sql": [
        "INNER JOIN vs LEFT JOIN",
        "primary key vs foreign key",
        "GROUP BY with HAVING",
        "WHERE vs HAVING",
        "database indexes",
        "normalization",
        "DELETE vs TRUNCATE",
        "finding duplicate rows",
    ],
}


HR_FOCUS = [
    "introducing yourself and summarizing your background",
    "explaining why you want this role",
    "describing your strengths and areas for improvement",
    "handling constructive feedback",
    "describing a challenge you overcame",
    "working effectively with a team",
    "resolving a disagreement with a colleague",
    "managing competing priorities and deadlines",
    "learning a new skill quickly",
    "responding to a mistake at work",
    "adapting to changing requirements",
    "explaining why you are interested in the company",
]


BEHAVIORAL_FOCUS = [
    "describing a time you solved a difficult problem",
    "handling a disagreement within a team",
    "demonstrating leadership or initiative",
    "managing a tight deadline",
    "learning from a failure or mistake",
    "adapting to an unexpected change",
    "receiving and applying constructive feedback",
    "prioritizing multiple responsibilities",
    "collaborating with someone with a different perspective",
    "taking responsibility for an outcome",
]


# =========================================================
# INPUT NORMALIZATION
# =========================================================

def clean_input(value, default="General"):
    if value is None:
        return default

    value = " ".join(str(value).split())
    return value or default


def normalize_question(question):
    if not question:
        return ""

    question = str(question).lower().strip()
    question = re.sub(r"^\s*\d+[\.\)\-:]\s*", "", question)
    question = re.sub(r"[^\w\s]", " ", question)
    return " ".join(question.split())


def content_words(normalized_text):
    return {
        word
        for word in normalized_text.split()
        if word not in STOPWORDS
    }


def contains_any(text, terms):
    return any(term in text for term in terms)


def is_general_topic(topic):
    return normalize_question(topic) in {
        "general",
        "any",
        "all",
        "mixed",
        "general technical",
    }


def is_hr_topic(topic):
    return normalize_question(topic) in {
        "hr interview",
        "behavioral questions",
    }


# =========================================================
# HISTORY HELPERS
# =========================================================

def get_previous_questions(history):
    questions = []
    question_keys = [
        "question",
        "interviewer_question",
        "generated_question",
    ]

    for item in history or []:
        if not isinstance(item, dict):
            continue

        for key in question_keys:
            question = item.get(key)

            if isinstance(question, str) and question.strip():
                questions.append(question.strip())
                break

    unique_questions = []
    seen = set()

    for question in questions:
        normalized = normalize_question(question)

        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_questions.append(question)

    return unique_questions


def summarize_performance(history):
    """Compact, prompt-friendly summary of the last 3 answers."""
    lines = []

    for item in (history or [])[-3:]:
        if not isinstance(item, dict):
            continue

        name = item.get("subtopic") or item.get("topic") or "?"
        lines.append(
            f"- {name}: score {item.get('score', '?')} "
            f"({item.get('difficulty') or item.get('level') or '?'})"
        )

    return "\n".join(lines) or "No previous performance."


def get_weak_subtopics(history, threshold=65, max_repeats=3):
    """
    Subtopics where the candidate averages below the threshold,
    excluding ones already asked so often they would feel repetitive.
    """
    scores = {}

    for item in history or []:
        if not isinstance(item, dict):
            continue

        subtopic = item.get("subtopic")
        score = item.get("score")

        if subtopic and isinstance(score, (int, float)):
            scores.setdefault(subtopic, []).append(score)

    return [
        subtopic
        for subtopic, values in scores.items()
        if sum(values) / len(values) < threshold
        and len(values) < max_repeats
    ]


# =========================================================
# FOCUS PICKER
# =========================================================

def pick_focus(
    role,
    topic,
    previous_questions,
    rejected_questions,
    tried_focuses,
    weak_subtopics=None,
):
    """
    Choose a concrete concept for this attempt so the model has a
    specific target instead of copying whatever the RAG context says.
    Biased toward subtopics the candidate is weak in.
    """
    topic_text = normalize_question(topic)
    role_text = normalize_question(role)

    if is_general_topic(topic):
        pool = []

        for role_name in sorted(ROLE_SKILLS, key=len, reverse=True):
            if role_name in role_text:
                pool = ROLE_SKILLS[role_name]
                break

        pool = pool or ROLE_SKILLS["software developer"]

    elif topic_text == "hr interview":
        pool = HR_FOCUS

    elif topic_text == "behavioral questions":
        pool = BEHAVIORAL_FOCUS

    else:
        pool = TOPIC_SUBTOPICS.get(topic_text) or [topic]

    used_text = " ".join(
        normalize_question(q)
        for q in previous_questions + rejected_questions
    )

    candidates = [s for s in pool if s not in tried_focuses]

    unused = [
        s for s in candidates
        if not any(
            word in used_text
            for word in content_words(normalize_question(s))
        )
    ]

    weak = [
        s for s in (weak_subtopics or [])
        if s in pool and s not in tried_focuses
    ]

    if weak and random.random() < 0.6:
        choice = random.choice(weak)
    else:
        choice = random.choice(unused or candidates or pool)

    tried_focuses.add(choice)
    return choice


# =========================================================
# DUPLICATE DETECTION
# =========================================================

def is_duplicate_question(
    new_question,
    previous_questions,
    threshold=0.82,
    jaccard_threshold=0.75,
):
    normalized_new = normalize_question(new_question)

    if not normalized_new:
        return True

    new_words = content_words(normalized_new)

    for previous in previous_questions:
        normalized_previous = normalize_question(previous)

        if not normalized_previous:
            continue

        if normalized_new == normalized_previous:
            print("Exact duplicate matched:", previous)
            return True

        similarity = SequenceMatcher(
            None,
            normalized_new,
            normalized_previous,
        ).ratio()

        if similarity >= threshold:
            print(
                f"Similar question matched "
                f"(similarity={similarity:.2f}):",
                previous,
            )
            return True

        previous_words = content_words(normalized_previous)
        union = new_words | previous_words

        if union:
            jaccard = len(new_words & previous_words) / len(union)

            if jaccard >= jaccard_threshold:
                print(
                    f"Similar-content question matched "
                    f"(jaccard={jaccard:.2f}):",
                    previous,
                )
                return True

    return False


# =========================================================
# ROLE AND TOPIC RELEVANCE VALIDATION
# =========================================================

def is_relevant_question(
    question,
    role,
    topic,
    question_type="Technical",
    category="Conceptual",
    focus=None,
):
    text = normalize_question(question)
    role_text = normalize_question(role)
    topic_text = normalize_question(topic)
    type_text = normalize_question(question_type)

    # HR and behavioral questions should not require technical keywords.
    if is_hr_topic(topic):
        hr_signals = [
            "tell me about yourself",
            "introduce yourself",
            "summarize your background",
            "walk me through your resume",
            "walk me through your background",
            "describe your background",
            "your experience",
            "your career",
            "describe a time",
            "tell me about a time",
            "share an example",
            "give me an example",
            "how would you handle",
            "how do you handle",
            "how did you handle",
            "what would you do",
            "your strengths",
            "area for improvement",
            "constructive feedback",
            "work in a team",
            "team member",
            "teamwork",
            "disagreement",
            "conflict",
            "deadline",
            "challenge",
            "mistake",
            "failure",
            "leadership",
            "initiative",
            "prioritize",
            "prioritizing",
            "motivation",
            "why do you want",
            "why are you interested",
            "adapt to",
            "adaptability",
            "learn a new skill",
            "different perspective",
            "take responsibility",
            "professional growth",
            "career goals",
        ]

        if not contains_any(text, hr_signals):
            print(
                "Rejected: question does not match the HR/behavioral topic."
            )
            return False

        return True

    # Prevent machine-learning questions for unrelated roles.
    ml_terms = [
        "machine learning",
        "deep learning",
        "overfitting",
        "underfitting",
        "regularization",
        "neural network",
        "gradient descent",
        "supervised learning",
        "unsupervised learning",
    ]

    ml_roles = [
        "machine learning",
        "deep learning",
        "ai ml",
        "artificial intelligence",
        "data scientist",
        "ml engineer",
    ]

    is_ml_role = contains_any(role_text, ml_roles)
    is_ml_topic = contains_any(topic_text, ml_roles)

    if (
        contains_any(text, ml_terms)
        and not is_ml_role
        and not is_ml_topic
    ):
        print("Rejected: machine-learning question for unrelated role.")
        return False

    # Reject process / management theory for technical roles unless
    # the user explicitly asked for it as the topic.
    if (
        contains_any(text, LOW_PRIORITY_GENERAL_TOPICS)
        and not contains_any(
            topic_text,
            [
                "sdlc",
                "agile",
                "scrum",
                "software engineering",
                "project management",
            ],
        )
    ):
        print("Rejected: process/management question for technical role.")
        return False

    # General topic: require a role skill signal.
    if is_general_topic(topic):
        matched_role = None

        for role_name in sorted(ROLE_SKILLS, key=len, reverse=True):
            if role_name in role_text:
                matched_role = role_name
                break

        if (
            matched_role
            and not contains_any(text, ROLE_SKILLS[matched_role])
        ):
            print(
                f"Rejected: question does not contain a clear "
                f"'{matched_role}' skill signal."
            )
            return False

    # Coding question type.
    if "coding" in type_text or "programming" in type_text:
        coding_signals = [
            "write code",
            "write a function",
            "implement",
            "program",
            "code",
            "algorithm",
            "solve",
            "return the",
            "given an array",
            "given a string",
        ]

        if not contains_any(text, coding_signals):
            print("Rejected: question does not match Coding question type.")
            return False

    # Specific topic: question must stay on topic.
    if not is_general_topic(topic):
        topic_aliases = {
            "dsa": [
                "data structure", "algorithm", "array", "string",
                "linked list", "stack", "queue", "tree", "graph",
                "sorting", "searching", "complexity", "hashmap",
                "hash map", "binary search",
            ],
            "oops": [
                "object oriented", "oop", "class", "object",
                "inheritance", "polymorphism", "encapsulation",
                "abstraction", "constructor", "overloading",
                "overriding", "interface", "abstract",
            ],
            "object oriented programming": [
                "object oriented", "oop", "class", "object",
                "inheritance", "polymorphism", "encapsulation",
                "abstraction", "constructor", "overloading",
                "overriding", "interface", "abstract",
            ],
            "sql": [
                "sql", "query", "join", "table", "database",
                "primary key", "foreign key", "index", "group by",
                "normalization",
            ],
        }

        terms = list(topic_aliases.get(topic_text, [topic_text]))

        if focus:
            terms.extend(content_words(normalize_question(focus)))

        if not contains_any(text, terms):
            print(
                f"Rejected: question may not match requested topic "
                f"'{topic}'."
            )
            return False

    return True


# =========================================================
# PARSE LLAMA JSON
# =========================================================

def parse_question_response(response):
    if not response:
        raise ValueError("Empty LLM response")

    response = response.strip()

    response = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        response,
        flags=re.IGNORECASE,
    )
    response = re.sub(r"\s*```\s*$", "", response)

    try:
        data = json.loads(response)

    except json.JSONDecodeError:
        start = response.find("{")
        end = response.rfind("}")

        if start == -1 or end <= start:
            raise ValueError(
                f"No complete JSON object found. "
                f"Raw response: {response[:500]}"
            )

        data = json.loads(response[start:end + 1])

    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")

    question = str(data.get("question", "")).strip()
    expected_answer = str(data.get("expected_answer", "")).strip()

    if not question:
        raise ValueError("Generated question is empty")

    if not expected_answer:
        raise ValueError("Generated expected answer is empty")

    question = re.sub(
        r"^\s*\d+[\.\)\-:]\s*",
        "",
        question,
    ).strip()

    prefixes = [
        "Here is your question:",
        "Here is the interview question:",
        "Question:",
        "Interview Question:",
    ]

    for prefix in prefixes:
        if question.lower().startswith(prefix.lower()):
            question = question[len(prefix):].strip()

    question = " ".join(question.split())
    expected_answer = " ".join(expected_answer.split())

    return question, expected_answer


# =========================================================
# LLM CALL
# =========================================================
def call_llm(prompt, temperature):
    return ask_llama(
        prompt,
        max_tokens=NUM_PREDICT,
        temperature=temperature,
        response_format="json",
    )



# =========================================================
# PROMPT BUILDER
# =========================================================

def build_prompt(
    role,
    company,
    topic,
    difficulty,
    question_type,
    category,
    context,
    performance,
    previous_questions_text,
    rejected_questions,
    profile_text,
    focus,
):
    rejected_text = "\n".join(
        f"- {question}" for question in rejected_questions
    ) or "None"

    difficulty_text = DIFFICULTY_GUIDE.get(
        difficulty,
        DIFFICULTY_GUIDE["Medium"],
    )

    hr_mode = is_hr_topic(topic)

    interview_style = (
        "an HR interviewer assessing communication, motivation, teamwork, "
        "adaptability, and professional behavior"
        if hr_mode
        else "a technical interviewer assessing role-specific skills"
    )

    if hr_mode:
        answer_instructions = """
- Use a realistic sample response in simple, professional language.
- For behavioral questions, use a concise example with action and outcome.
- For introductory questions, provide a short sample introduction.
- Do not require technical details unless they are relevant to the question.
- Do not include placeholders such as [insert example] or [your experience].
- Keep the answer around 20 to 50 words, at most three sentences.
"""
    else:
        answer_instructions = """
- Be technically accurate and use simple professional language.
- Keep the answer between 20 and 35 words, at most two sentences.
- Do not include code.
- Do not include placeholders such as [insert example] or [your experience].
"""

    return f"""
You are an expert interviewer acting as {interview_style} for entry-level candidates.

Generate exactly ONE interview question and ONE expected answer.

DETAILS:
Role: "{role}"
Company: "{company}"
Topic: "{topic}"
Question Type: "{question_type}"
Category: "{category}"

FOCUS CONCEPT (mandatory):
The question MUST be directly about: {focus}
Ignore any reference material that is unrelated to this concept.

DIFFICULTY ({difficulty}):
{difficulty_text}

RULES:
- Ask exactly ONE clear, entry-level question about the focus concept.
- For HR or behavioral topics, assess professional behavior, communication,
  teamwork, motivation, adaptability, or problem-solving through a realistic
  interview question.
- For technical topics, test a practical skill for the role "{role}".
- It must differ from every question in the lists below.
- Do not ask about requirements engineering, SDLC, or project management.
- For "HR Interview", introductory questions such as "Tell me about yourself"
  are allowed.
- For "Behavioral Questions", focus on a specific past experience or situation.

REFERENCE MATERIAL (use only if relevant to the focus concept):
{context}

COMPANY STYLE:
{profile_text}

RECENT PERFORMANCE:
{performance}

ALREADY ASKED (do not repeat or paraphrase):
{previous_questions_text}

REJECTED (do not repeat or paraphrase):
{rejected_text}

EXPECTED ANSWER:
{answer_instructions}

OUTPUT RULES:
- Return only valid JSON, no Markdown, no code fences, no commentary.
- No literal line breaks inside JSON string values.

OUTPUT FORMAT:
{{
    "question": "One interview question about the focus concept",
    "expected_answer": "A concise and appropriate sample answer."
}}
"""


# =========================================================
# COMPANY PROFILE LOOKUP
# =========================================================

def get_company_profile(company):
    company_key = normalize_question(company)

    for key, profile in COMPANY_STYLE.items():
        if normalize_question(key) == company_key:
            return profile

    for key, profile in COMPANY_STYLE.items():
        normalized_key = normalize_question(key)

        if (
            normalized_key
            and (
                normalized_key in company_key
                or company_key in normalized_key
            )
        ):
            return profile

    return {}


# =========================================================
# RAG HELPER
# =========================================================

def get_context(role, company, topic, focus):
    """Retrieve relevant context, dropping it if harmful or off-role."""

    # Avoid injecting unrelated technical documents into HR questions.
    # This preserves question generation while bypassing technical RAG.
    if is_hr_topic(topic):
        print("HR/behavioral topic detected: skipping technical RAG retrieval.")
        return ""

    try:
        context = retrieve_context(
            role=role,
            company=company,
            topic=focus if is_general_topic(topic) else f"{topic} {focus}",
        )

        if isinstance(context, dict):
            context = context.get("context", "")
        elif isinstance(context, list):
            context = "\n".join(str(item) for item in context)

        context = str(context or "").strip()

    except Exception as error:
        print("RAG retrieval error:", error)
        return ""

    if not context:
        return ""

    print("RAG preview:", context[:200].replace("\n", " "))

    lowered = context.lower()

    focus_terms = {
        word[:6]
        for word in content_words(normalize_question(focus))
        if len(word) > 3
    }

    if not is_general_topic(topic):
        focus_terms |= {
            word[:6]
            for word in content_words(normalize_question(topic))
            if len(word) > 3
        }

    on_focus = any(term in lowered for term in focus_terms)

    role_terms = []

    for role_name in sorted(ROLE_SKILLS, key=len, reverse=True):
        if role_name in normalize_question(role):
            role_terms = ROLE_SKILLS[role_name]
            break

    on_role = contains_any(lowered, role_terms) if role_terms else True
    off_topic = contains_any(lowered, LOW_PRIORITY_GENERAL_TOPICS)

    if off_topic and not on_focus:
        print("RAG context dropped: process/management material.")
        return ""

    if not on_focus and not on_role:
        print("RAG context dropped: unrelated to focus and role.")
        return ""

    return context[:1200]


# =========================================================
# GENERATE INTERVIEW QUESTION
# =========================================================

def generate_question(
    role,
    company,
    topic,
    history=None,
    question_type="Technical",
    category="Conceptual",
):
    total_start = time.perf_counter()

    history = history or []

    role = clean_input(role)
    company = clean_input(company)
    topic = clean_input(topic)
    question_type = clean_input(question_type, "Technical")
    category = clean_input(category, "Conceptual")

    difficulty = adjust_difficulty(history)
    performance = summarize_performance(history)
    weak_subtopics = get_weak_subtopics(history)

    previous_questions = get_previous_questions(history)

    print(f"Previous questions available: {len(previous_questions)}")
    print(f"Requested role: {role!r}")
    print(f"Requested topic: {topic!r}")
    print(f"Requested company: {company!r}")
    print(f"Difficulty: {difficulty}")
    print(f"Weak subtopics: {weak_subtopics}")

    previous_questions_text = "\n".join(
        f"- {question}"
        for question in previous_questions[-30:]
    ) or "No previous questions available."

    # -----------------------------------------------------
    # COMPANY PROFILE
    # -----------------------------------------------------

    profile = get_company_profile(company)

    profile_text = (
        f"Description: {profile.get('description', 'General technical interview.')}\n"
        f"Interview Style: {', '.join(profile.get('interview_style', []))}\n"
        f"Main Focus: {', '.join(profile.get('focus', []))}\n"
        f"Preferred Topics: {', '.join(profile.get('preferred_topics', []))}\n"
        f"Coding Level: {profile.get('coding_level', 'Intermediate')}\n"
        f"Behavioral Round: {'Yes' if profile.get('behavioral', False) else 'No'}"
    )

    print("Company profile matched:", bool(profile))

    # -----------------------------------------------------
    # GENERATE AND VALIDATE
    # -----------------------------------------------------

    rejected_questions = []
    tried_focuses = set()
    question = ""
    expected_answer = ""
    focus = topic
    llm_time = 0.0
    rag_time = 0.0
    attempt_time = 0.0

    for attempt in range(MAX_ATTEMPTS):
        attempt_start = time.perf_counter()

        try:
            print(f"\nLLM generation attempt: {attempt + 1}")

            focus = pick_focus(
                role,
                topic,
                previous_questions,
                rejected_questions,
                tried_focuses,
                weak_subtopics=weak_subtopics,
            )
            print("Focus concept:", focus)

            rag_start = time.perf_counter()
            context = get_context(role, company, topic, focus)
            rag_time += time.perf_counter() - rag_start

            if not context:
                context = (
                    "No reference material. Use your own knowledge to "
                    "generate a relevant interview question."
                )

            print(f"RAG context characters: {len(context)}")

            prompt = build_prompt(
                role=role,
                company=company,
                topic=topic,
                difficulty=difficulty,
                question_type=question_type,
                category=category,
                context=context,
                performance=performance,
                previous_questions_text=previous_questions_text,
                rejected_questions=rejected_questions,
                profile_text=profile_text,
                focus=focus,
            )

            # Raise temperature on each retry to break out of loops.
            temperature = min(0.5 + 0.15 * attempt, 1.0)

            llm_start = time.perf_counter()
            try:
                response = call_llm(prompt, temperature=temperature)
            finally:
                llm_time += time.perf_counter() - llm_start

            
            if not response:
                print(
                    f"LLM returned an empty response on attempt "
                    f"{attempt + 1}. Check llama_client logs."
                )
                continue

            print("Raw response:", repr(response))


            candidate_question, candidate_answer = (
                parse_question_response(response)
            )

            if not is_relevant_question(
                candidate_question,
                role,
                topic,
                question_type,
                category,
                focus=focus,
            ):
                print("Irrelevant question rejected:", candidate_question)
                rejected_questions.append(candidate_question)
                continue

            if is_duplicate_question(
                candidate_question,
                previous_questions + rejected_questions,
            ):
                print("Duplicate question rejected:", candidate_question)
                rejected_questions.append(candidate_question)
                continue

            question = candidate_question
            expected_answer = candidate_answer
            break

     
        
        except Exception as error:
            print(
                f"Generation attempt {attempt + 1} failed: "
                f"{type(error).__name__}: {error!r}"
            )


        finally:
            attempt_time += time.perf_counter() - attempt_start

    # -----------------------------------------------------
    # HANDLE FAILURE
    # -----------------------------------------------------

    if not question or not expected_answer:
        total_time = time.perf_counter() - total_start

        print("\n========== PERFORMANCE ==========")
        print(f"RAG time: {rag_time:.2f} seconds")
        print(f"LLM time: {llm_time:.2f} seconds")
        print(f"Attempt time: {attempt_time:.2f} seconds")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Rejected questions: {rejected_questions}")
        print("=================================")

        raise RuntimeError(
            f"Unable to generate a valid, non-duplicate question "
            f"for role '{role}' and topic '{topic}' "
            f"after {MAX_ATTEMPTS} attempts. "
            f"Rejected questions: {rejected_questions}"
        )

    # -----------------------------------------------------
    # CLEAN EXPECTED ANSWER
    # -----------------------------------------------------

    expected_answer = re.sub(
        r"```.*?```",
        "",
        expected_answer,
        flags=re.DOTALL,
    ).strip()

    # Remove accidental placeholder text if the model produces it.
    expected_answer = re.sub(
        r"\[[^\]]*\]",
        "",
        expected_answer,
    )
    expected_answer = " ".join(expected_answer.split())

    words = expected_answer.split()

    if len(words) > 80:
        expected_answer = " ".join(words[:80]).rstrip(".,;:") + "."

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    result = {
        "question": question,
        "expected_answer": expected_answer,
        "difficulty": difficulty,
        "topic": topic,
        "subtopic": focus,
        "company": company,
        "role": role,
    }

    print("\n========== FINAL GENERATED QUESTION ==========")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("===============================================")

    total_time = time.perf_counter() - total_start

    print("\n========== PERFORMANCE ==========")
    print(f"RAG time: {rag_time:.2f} seconds")
    print(f"LLM time: {llm_time:.2f} seconds")
    print(f"Attempt time: {attempt_time:.2f} seconds")
    print(f"Total time: {total_time:.2f} seconds")
    print("=================================")

    return result