import json
import logging
import re
import traceback
from typing import List

from llama.llama_client import ask_llama


def generate_interview_report(
    role: str,
    company: str,
    questions: List[dict],
    evaluations: List[dict]
):
    """
    Generate ONE detailed final interview feedback report.

    This function does NOT evaluate answers.

    /evaluate is responsible for:
        - llm_score
        - smith_waterman_score
        - final_score

    This function is responsible ONLY for:
        - overall interview analysis
        - strengths
        - weaknesses
        - recommendations
        - final assessment
    """

    try:

        # =====================================================
        # NO EVALUATIONS
        # =====================================================

        if not evaluations:

            return {
                "success": False,
                "overall_score": 0,
                "percentage": 0,
                "classification": "No Evaluation",
                "total_questions": 0,

                "summary":
                    "No answers were submitted.",

                "strengths": [],
                "weaknesses": [],
                "recommendations": [],

                "final_assessment":
                    "No interview performance could be evaluated.",

                "scores": []
            }

        # =====================================================
        # CALCULATE OVERALL SCORE
        # =====================================================

        scores = []

        for evaluation in evaluations:

            score = float(
                evaluation.get(
                    "final_score",
                    0
                )
            )

            score = max(
                0,
                min(score, 100)
            )

            scores.append(score)

        overall_score = round(
            sum(scores) / len(scores),
            2
        )

        # =====================================================
        # PREPARE INTERVIEW DATA
        # ====================================================
        interview_data = []

        for index, evaluation in enumerate(evaluations):

            question = ""

            if index < len(questions):
                question = questions[index].get("question", "")

            interview_data.append({
                "question": question,
                "student_answer": evaluation.get(
                    "student_answer",
                    ""
                ),
                "llm_score": evaluation.get(
                    "llm_score",
                    0
                ),
                "smith_waterman_score": evaluation.get(
                    "smith_waterman_score",
                    0
                ),
                "final_score": evaluation.get(
                    "final_score",
                    0
                )
            })



        # =====================================================
        # FINAL LLM FEEDBACK
        # =====================================================


        prompt = f"""
        You are an expert technical interview evaluator.

        Create ONE final interview report based ONLY on the
        provided interview data and already-calculated scores.

        Role: {role}
        Company: {company}
        Total Questions: {len(evaluations)}
        Overall Score: {overall_score}/100

        Interview data:
        {json.dumps(interview_data, separators=(",", ":"))}

        Analyze the candidate's overall:
        - technical knowledge
        - strengths
        - weaknesses
        - answer quality
        - interview readiness
        - areas needing improvement
        - practical recommendations
        - final assessment

        Rules:
        - Do NOT score or re-evaluate individual answers.
        - Use the provided scores exactly as given.
        - Do NOT give question-by-question feedback.
        - Do NOT invent skills or weaknesses.
        - Base everything only on the supplied questions, answers and scores.
        - Keep the report concise but useful.
        - Return ONLY valid JSON.

        Return exactly:
        {{
            "summary": "Overall performance analysis",
            "strengths": ["strength 1", "strength 2"],
            "weaknesses": ["weakness 1", "weakness 2"],
            "recommendations": ["recommendation 1", "recommendation 2"],
            "final_assessment": "Final interview assessment"
        }}
        """



        llm_response = ask_llama(
            prompt,
            max_tokens=800,
            temperature=0.3,
            response_format="json",
        )

        # =====================================================
        # DEFAULT FEEDBACK
        # =====================================================

        feedback = {
            "summary":
                "Detailed AI feedback could not be generated.",

            "strengths": [],

            "weaknesses": [],

            "recommendations": [],

            "final_assessment":
                "The interview score was calculated successfully."
        }

        # =====================================================
        # PARSE LLM RESPONSE
        # =====================================================

        if llm_response:

            try:

                response_text = str(
                    llm_response
                ).strip()

                # Remove markdown code fences
                response_text = re.sub(
                    r"```json\s*",
                    "",
                    response_text,
                    flags=re.IGNORECASE
                )

                response_text = re.sub(
                    r"```\s*",
                    "",
                    response_text
                ).strip()

                # Find JSON object if LLM added extra text
                match = re.search(
                    r"\{.*\}",
                    response_text,
                    re.DOTALL
                )

                if match:

                    response_text = match.group(0)

                parsed = json.loads(
                    response_text
                )

                feedback = {

                    "summary":
                        parsed.get(
                            "summary",
                            feedback["summary"]
                        ),

                    "strengths":
                        parsed.get(
                            "strengths",
                            []
                        ),

                    "weaknesses":
                        parsed.get(
                            "weaknesses",
                            []
                        ),

                    "recommendations":
                        parsed.get(
                            "recommendations",
                            []
                        ),

                    "final_assessment":
                        parsed.get(
                            "final_assessment",
                            feedback["final_assessment"]
                        )
                }

            except Exception as error:

                logging.error(
                    "Final feedback JSON parsing error: %s",
                    error
                )

                logging.error(
                    "Raw LLM response: %s",
                    llm_response
                )

        # =====================================================
        # CLASSIFICATION
        # =====================================================

        if overall_score >= 85:

            classification = "Excellent"

        elif overall_score >= 75:

            classification = "Very Good"

        elif overall_score >= 65:

            classification = "Good"

        elif overall_score >= 50:

            classification = "Needs Improvement"

        else:

            classification = "Beginner"

        # =====================================================
        # SCORE INFORMATION
        # =====================================================

        score_details = []

        for index, evaluation in enumerate(evaluations):

            score_details.append({

                "question_number":
                    index + 1,

                "llm_score":
                    round(
                        float(
                            evaluation.get(
                                "llm_score",
                                0
                            )
                        ),
                        2
                    ),

                "smith_waterman_score":
                    round(
                        float(
                            evaluation.get(
                                "smith_waterman_score",
                                0
                            )
                        ),
                        2
                    ),

                "final_score":
                    round(
                        float(
                            evaluation.get(
                                "final_score",
                                0
                            )
                        ),
                        2
                    )
            })

        # =====================================================
        # FINAL RESPONSE
        # =====================================================

        return {

            "success": True,

            "overall_score":
                overall_score,

            "percentage":
                overall_score,

            "classification":
                classification,

            "total_questions":
                len(evaluations),

            # Final combined feedback
            "summary":
                feedback["summary"],

            "strengths":
                feedback["strengths"],

            "weaknesses":
                feedback["weaknesses"],

            "recommendations":
                feedback["recommendations"],

            "final_assessment":
                feedback["final_assessment"],

            # Scores only — no individual feedback
            "scores":
                score_details,

            "evaluation_method": {

                "llm_weight":
                    "80%",

                "smith_waterman_weight":
                    "20%",

                "formula":
                    "Final Score = (LLM Score × 0.80) + (Smith-Waterman Score × 0.20)",

                "overall_score":
                    "Average of all individual final scores"
            },

            "role":
                role,

            "company":
                company
        }

    except Exception as error:

        logging.error(
            traceback.format_exc()
        )

        return {

            "success": False,

            "overall_score": 0,

            "percentage": 0,

            "classification":
                "Evaluation Error",

            "total_questions":
                len(evaluations)
                if evaluations
                else 0,

            "summary":
                "Unable to generate final interview feedback.",

            "strengths": [],

            "weaknesses": [],

            "recommendations": [],

            "final_assessment":
                "An error occurred while generating the final report.",

            "scores": [],

            "error":
                str(error)
        }