import axios from "axios";
import FormData from "form-data";

const AI_API = (
  process.env.AI_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const TRANSCRIBE_URL = `${AI_API}/transcribe-audio`;

export const transcribeAudio = async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({
        message: "No audio file was uploaded.",
      });
    }

    const formData = new FormData();

    formData.append("audio", req.file.buffer, {
      filename: req.file.originalname || "recording.webm",
      contentType: req.file.mimetype || "audio/webm",
    });

    console.log("Calling audio transcription API:", TRANSCRIBE_URL);

    const response = await axios.post(
      TRANSCRIBE_URL,
      formData,
      {
        headers: formData.getHeaders(),
        timeout: 120000,
        maxBodyLength: Infinity,
      }
    );

    return res.status(200).json({
      transcript: response.data.transcript,
    });
  } catch (error) {
    console.error(
      "Audio transcription error:",
      error.response?.data || error.message
    );

    return res.status(error.response?.status || 500).json({
      message: "Audio transcription failed.",
    });
  }
};
