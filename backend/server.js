import dotenv from "dotenv";
dotenv.config();

import express from "express";
import cors from "cors";
import interviewRoutes from "./routes/interviewRoutes.js";
import questionRoutes from "./routes/questionRoutes.js";
import pool from "./config/db.js";
import resumeRoutes from "./routes/resumeRoutes.js";
import selectionRoutes from "./routes/selectionRoutes.js";
import authRoutes from "./routes/authRoutes.js";
import codeRunnerRoutes from "./routes/codeRunnerRoutes.js";
import adminRoutes from "./routes/adminRoutes.js";

const app = express();

app.get("/", (req, res) => {
  res.status(200).json({
    success: true,
    message: "Backend API is running 🚀",
  });
});

// Middleware
app.use(cors({
  origin: (origin, callback) => {
    const configuredOrigins = (process.env.CLIENT_URL || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    const allowedOrigins = new Set([
      "http://localhost:5173",
      "http://127.0.0.1:5173",
      ...configuredOrigins,
    ]);

    if (!origin || allowedOrigins.has(origin)) {
      return callback(null, true);
    }

    return callback(new Error("Origin is not allowed by CORS"));
  }
}));
app.use(express.json());


// Routes
app.use("/api/interview", interviewRoutes);
app.use("/api/questions", questionRoutes);
app.use("/api/resume", resumeRoutes);
app.use("/api", selectionRoutes);
app.use("/api/auth", authRoutes);
app.use("/api/code", codeRunnerRoutes);
app.use("/api/admin", adminRoutes);

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: "Route not found" });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: "Something went wrong" });
});

// Start server
const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

// DB test
pool.query("SELECT 1")
  .then(() => console.log("DB Connected ✅"))
  .catch(err => console.error("DB Error ❌", err));