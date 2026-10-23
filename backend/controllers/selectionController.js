
import pool from "../config/db.js";
import axios from "axios";

// =========================================
// AI API CONFIGURATION
// =========================================

const AI_API = (
  process.env.AI_API_URL ||
  "http://localhost:8000"
).replace(/\/+$/, "");

const AI_VTU_QUESTION_URL =
  `${AI_API}/generate-vtu-question`;

// =========================================
// GET ALL ROLES
// =========================================

export const getRoles = async (req, res) => {
  try {
    const result = await pool.query(
      "SELECT id, role_name FROM roles ORDER BY role_name ASC"
    );

    return res.json(result.rows);
  } catch (err) {
    console.error("Selection Error (Roles):", err);

    return res.status(500).json({
      error: "Failed to fetch roles",
    });
  }
};

// =========================================
// GET ALL COMPANIES
// =========================================

export const getCompanies = async (req, res) => {
  try {
    const result = await pool.query(
      "SELECT id, company_name FROM companies ORDER BY company_name ASC"
    );

    return res.json(result.rows);
  } catch (err) {
    console.error("Selection Error (Companies):", err);

    return res.status(500).json({
      error: "Failed to fetch companies",
    });
  }
};

// =========================================
// GET ROLES BY COMPANY
// =========================================

export const getRolesByCompany = async (req, res) => {
  const { companyId } = req.params;

  try {
    const query = `
      SELECT r.id, r.role_name
      FROM roles r
      INNER JOIN company_roles cr ON r.id = cr.role_id
      WHERE cr.company_id = $1
      ORDER BY r.role_name ASC
    `;

    const result = await pool.query(query, [companyId]);

    return res.json(result.rows);
  } catch (err) {
    console.error("Selection Error (Company Roles):", err);

    return res.status(500).json({
      error: "Failed to fetch filtered roles",
    });
  }
};

// =========================================
// GET VTU QUESTIONS
// =========================================

export const getVtuQuestions = async (req, res) => {
  try {
    // 1. Fetch existing VTU questions
    const existingResult = await pool.query(`
      SELECT
        q.id,
        q.question_text,
        q.expected_answer,
        q.syllabus_id,
        s.subject_name,
        s.module_name,
        s.topic_name
      FROM questions q
      JOIN vtu_syllabus s ON s.id = q.syllabus_id
      WHERE q.syllabus_id IS NOT NULL
      ORDER BY RANDOM()
      LIMIT 3
    `);

    const questions = [...existingResult.rows];

    // 2. Fetch syllabus topics
    const syllabusResult = await pool.query(`
      SELECT id, subject_name, module_name, topic_name
      FROM vtu_syllabus
      ORDER BY RANDOM()
    `);

    // 3. Generate additional questions until we have 10
    for (const syllabus of syllabusResult.rows) {
      if (questions.length >= 10) {
        break;
      }

      try {
        // Normalize URL to prevent accidental double slashes
        const aiUrl =
          `${AI_API.replace(/\/+$/, "")}/generate-vtu-question`;

        console.log("Calling VTU AI API:", aiUrl);
        console.log("VTU topic:", syllabus.topic_name);

        const aiResponse = await axios.post(
          aiUrl,
          {
            subject: syllabus.subject_name,
            module: syllabus.module_name,
            topic: syllabus.topic_name,
          },
          {
            timeout: 120000,
            headers: {
              "Content-Type": "application/json",
            },
          }
        );

        const generated = aiResponse.data;

        // Validate AI response
        if (
          typeof generated?.question !== "string" ||
          !generated.question.trim() ||
          typeof generated?.expected_answer !== "string" ||
          !generated.expected_answer.trim()
        ) {
          console.warn(
            "Skipping invalid AI response for topic:",
            syllabus.topic_name
          );

          continue;
        }

        // 4. Save generated question
        const saved = await pool.query(
          `INSERT INTO questions (
            question_text,
            syllabus_id,
            difficulty_level,
            question_type,
            expected_answer,
            generated_by,
            category,
            ai_difficulty
          )
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
          RETURNING
            id,
            question_text,
            expected_answer,
            syllabus_id`,
          [
            generated.question.trim(),
            syllabus.id,
            String(generated.difficulty || "Medium").toLowerCase(),
            "technical",
            generated.expected_answer.trim(),
            "llama",
            syllabus.module_name,
            generated.difficulty || "Medium",
          ]
        );

        questions.push({
          ...saved.rows[0],
          subject_name: syllabus.subject_name,
          module_name: syllabus.module_name,
          topic_name: syllabus.topic_name,
        });

        console.log(
          "VTU question generated and saved:",
          syllabus.topic_name
        );
      } catch (aiError) {
        console.error(
          "VTU generation failed:",
          {
            topic: syllabus.topic_name,
            url: AI_VTU_QUESTION_URL,
            status: aiError.response?.status,
            response:
              aiError.response?.data || aiError.message,
          }
        );

        // Continue with other topics if one generation fails
      }
    }

    // 5. Return questions
    if (questions.length === 0) {
      return res.status(404).json({
        message:
          "No VTU questions could be retrieved or generated.",
      });
    }

    return res.json(questions.slice(0, 10));
  } catch (err) {
    console.error("VTU question selection error:", err);

    return res.status(500).json({
      error: "Failed to fetch VTU questions.",
    });
  }
};
