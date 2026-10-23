import axios from "axios";
import pdfParse from "pdf-parse/lib/pdf-parse.js";

const PYTHON_BACKEND_URL = process.env.AI_API_URL  || "http://localhost:8000";

// =====================
// Generate Job Description
// =====================
export const generateJobDescription = async (req, res) => {
  const role = String(req.body?.role || "").trim();

  if (!role) {
    return res.status(400).json({
      error: "Please select a target role",
    });
  }

  try {
    const response = await axios.post(
      `${PYTHON_BACKEND_URL}/generate-job-description`,
      { role },
      { timeout: 60000 }
    );

    const jobDescription = response.data?.job_description;

    if (typeof jobDescription !== "string" || !jobDescription.trim()) {
      return res.status(502).json({
        error: "The AI service returned an invalid job description",
      });
    }

    return res.json({
      success: true,
      role,
      jobDescription: jobDescription.trim(),
    });
  } catch (error) {
    console.error(
      "Job description generation error:",
      error.response?.data || error.message
    );

    const isTimeout = error.code === "ECONNABORTED" || error.code === "ETIMEDOUT";

    return res.status(502).json({
      error: isTimeout
        ? "Job description generation timed out. Please try again."
        : "Unable to generate a job description right now.",
    });
  }
};

// =====================
// Extract Resume Text
// =====================
export const extractResumeText = async (req, res) => {
  try {
    const file = req.file;

    if (!file?.buffer) {
      return res.status(400).json({ error: "No file uploaded" });
    }

    const data = await pdfParse(file.buffer);

    return res.json({
      text: data.text || "",
    });

  } catch (error) {
    console.error("PDF Parse Error FULL:", error);

    return res.status(500).json({
      error: "Failed to parse PDF",
    });
  }
};

// =====================
// Analyze Resume
// =====================
export const analyzeResume = async (req, res) => {

  try {

    const file = req.file;


    if (!file?.buffer) {

      return res.status(400).json({
        error:"No file uploaded"
      });

    }


    const data = await pdfParse(file.buffer);


    const extractedText = (data.text || "")
      .replace(/\r/g,"")
      .replace(/[ \t]+/g," ")
      .trim();



    if(!extractedText){

      return res.status(400).json({
        error:"Could not extract text from resume"
      });

    }



    const response = await axios.post(

      `${PYTHON_BACKEND_URL}/analyze-resume`,

      {

        text: extractedText,

        role:
          req.body.role || "Software Engineer",

        job_description:
          req.body.job_description || ""

      },

      {
        timeout:60000
      }

    );


    return res.json(response.data);



  } catch(err){


    console.error(
      "Resume Error:",
      err.response?.data || err.message
    );


    return res.status(500).json({

      error:"Resume analysis failed",

      details:
        err.response?.data || err.message

    });

  }

};