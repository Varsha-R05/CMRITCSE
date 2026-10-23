import json
import re

from llama.llama_client import ask_llama
from smith_waterman import smith_waterman


# ============================================================
# LLM SCORE EVALUATION
# ============================================================

def llm_evaluate_answer(
    question,
    answer,
    role="General",
    company="General"
):
    prompt = f"""
Evaluate this interview answer.

Question:
{question}

Candidate answer:
{answer}
Role:
{role}

Company:
{company}

Give a score from 0 to 100 based on:
- correctness
- technical understanding
- relevance
- completeness

Then provide a short ideal answer.

Return ONLY JSON:
{{
  "score": 0,
  "ideal_answer": "short correct answer"
}}
"""

    response = ask_llama(prompt)

    if not response:
        return {
            "score": 0,
            "ideal_answer": ""
        }

    try:
        response = response.strip()

        response = re.sub(
            r"```json\s*|\s*```",
            "",
            response,
            flags=re.IGNORECASE
        )

        match = re.search(
            r"\{.*\}",
            response,
            re.DOTALL
        )

        if match:
            response = match.group(0)

        data = json.loads(response)

        score = float(data.get("score", 0))

        return {
            "score": max(0, min(score, 100)),
            "ideal_answer": str(
                data.get("ideal_answer", "")
            )
        }

    except Exception as error:
        print("LLM JSON parsing error:", error)

        return {
            "score": 0,
            "ideal_answer": ""
        }


# ============================================================
# MAIN ANSWER EVALUATION
# ============================================================

def evaluate_answer(
    ans,
    question="",
    role="General",
    company="General"
):
    """
    Evaluate one interview answer.

    Evaluation:

        LLM             -> 80%
        Smith-Waterman  -> 20%

    This function ONLY calculates the individual score.

    Detailed interview feedback is generated later by:

        interview_feedback.py

    through /evaluate-interview.
    """

    print(
        "=============================================="
    )

    print(
        "DEBUG: Evaluating Interview Answer"
    )

    print(
        f"Role: {role}"
    )

    print(
        f"Company: {company}"
    )

    print(
        f"Question: {question}"
    )

    print(
        f"Candidate Answer: {ans}"
    )

    print(
        "=============================================="
    )


    # ========================================================
    # VALIDATE ANSWER
    # ========================================================

    if not ans or not str(ans).strip():

        return {
            "llm_score": 0,
            "smith_waterman_score": 0,
            "keyword_match_score": 0,
            "final_score": 0,
            "result": "Incorrect",
            "ideal_answer": "",
            "evaluation_method": {
                "llm_weight": "80%",
                "smith_waterman_weight": "20%"
            }
        }


    # ========================================================
    # VALIDATE QUESTION
    # ========================================================

    if not question or not str(question).strip():

        return {
            "llm_score": 0,
            "smith_waterman_score": 0,
            "keyword_match_score": 0,
            "final_score": 0,
            "result": "Evaluation Failed",
            "ideal_answer": "",
            "evaluation_method": {
                "llm_weight": "80%",
                "smith_waterman_weight": "20%"
            }
        }


    # ========================================================
    # 1. LLM EVALUATION
    # ========================================================

    llm_result = llm_evaluate_answer(
        question=question,
        answer=ans,
        role=role,
        company=company
    )

    llm_score = float(
        llm_result.get("score", 0)
    )


    # ========================================================
    # 2. GET IDEAL ANSWER
    # ========================================================

    ideal_answer = llm_result.get(
        "ideal_answer",
        ""
    )


    # ========================================================
    # 3. SMITH-WATERMAN
    # ========================================================

    sw_score = 0.0

    if ideal_answer:

        try:

            sw_score = smith_waterman(
                str(ans),
                str(ideal_answer)
            ) * 100

        except Exception as error:

            print(
                "Smith-Waterman error:",
                error
            )

            sw_score = 0.0


    sw_score = max(
        0,
        min(float(sw_score), 100)
    )


    # ========================================================
    # 4. FINAL SCORE
    #
    # LLM             = 80%
    # Smith-Waterman  = 20%
    # ========================================================

    final_score = (
        0.80 * llm_score
        +
        0.20 * sw_score
    )

    final_score = max(
        0,
        min(final_score, 100)
    )


    # ========================================================
    # 5. CLASSIFICATION
    # ========================================================

    result = get_result(
        final_score,
        role
    )


    # ========================================================
    # DEBUG
    # ========================================================

    print(
        "========== EVALUATION RESULT =========="
    )

    print(
        f"LLM Score: {llm_score:.2f}"
    )

    print(
        f"Smith-Waterman Score: {sw_score:.2f}"
    )

    print(
        f"Final Score: {final_score:.2f}"
    )

    print(
        f"Result: {result}"
    )

    print(
        "========================================"
    )


    # ========================================================
    # RETURN
    # ========================================================

    return {

        "llm_score": round(
            llm_score,
            2
        ),

        "smith_waterman_score": round(
            sw_score,
            2
        ),

        # Backward compatibility
        "keyword_match_score": round(
            sw_score,
            2
        ),

        "final_score": round(
            final_score,
            2
        ),

        "result": result,

        # Needed internally for scoring/debugging
        # but NOT displayed as individual feedback
        "ideal_answer": ideal_answer,

        "evaluation_method": {
            "llm_weight": "80%",
            "smith_waterman_weight": "20%"
        },

        "context": {
            "role": role,
            "company": company
        }
    }


# ============================================================
# RESULT CLASSIFICATION
# ============================================================

def get_result(
    score,
    role="General"
):
    """
    Classify candidate performance.
    """

    is_senior = any(
        word in role.lower()
        for word in [
            "senior",
            "lead",
            "architect",
            "expert"
        ]
    )

    correct_threshold = (
        85 if is_senior else 75
    )

    partial_threshold = (
        60 if is_senior else 50
    )

    if score >= correct_threshold:

        return (
            f"Correct ({role} Standard)"
        )

    elif score >= partial_threshold:

        return "Partially Correct"

    else:

        return "Incorrect"