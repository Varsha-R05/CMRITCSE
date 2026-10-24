import fs from "fs/promises";
import os from "os";
import path from "path";
import { spawn } from "child_process";
import { getLanguage } from "./languageRegistry.js";

const EXECUTION_TIMEOUT_MS = 3000;
const COMPILATION_TIMEOUT_MS = 10000;
const MAX_OUTPUT_BYTES = 1024 * 1024;

const STATUS = Object.freeze({
  ACCEPTED: { id: 3, description: "Accepted" },
  WRONG_ANSWER: { id: 4, description: "Wrong Answer" },
  TIME_LIMIT: { id: 5, description: "Time Limit Exceeded" },
  COMPILATION_ERROR: { id: 6, description: "Compilation Error" },
  RUNTIME_ERROR: { id: 7, description: "Runtime Error" },
  INTERNAL_ERROR: { id: 8, description: "Internal Error" },
});

const getExecutableName = () =>
  process.platform === "win32" ? "program.exe" : "program";

const runProcess = (
  command,
  args,
  options,
  timeoutMs,
  input = ""
) =>
  new Promise((resolve) => {
    let stdout = "";
    let stderr = "";
    let settled = false;

    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      resolve(result);
    };

    let child;

    try {
      child = spawn(command, args, {
        ...options,
        windowsHide: true,
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
      });
    } catch (error) {
      resolve({
        stdout: "",
        stderr: error.message,
        exitCode: null,
        spawnError: true,
      });
      return;
    }

    const timeout = setTimeout(() => {
      child.kill("SIGKILL");

      finish({
        stdout,
        stderr: "Time limit exceeded",
        exitCode: null,
        timedOut: true,
      });
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      const remaining = MAX_OUTPUT_BYTES - Buffer.byteLength(stdout);

      if (remaining > 0) {
        stdout += chunk.toString("utf8").slice(0, remaining);
      }
    });

    child.stderr.on("data", (chunk) => {
      const remaining = MAX_OUTPUT_BYTES - Buffer.byteLength(stderr);

      if (remaining > 0) {
        stderr += chunk.toString("utf8").slice(0, remaining);
      }
    });

    child.on("error", (error) => {
      finish({
        stdout,
        stderr: error.message,
        exitCode: null,
        spawnError: true,
      });
    });

    child.on("close", (exitCode) => {
      finish({
        stdout,
        stderr,
        exitCode,
        timedOut: false,
      });
    });

    if (input) {
      child.stdin.write(input);
    }

    child.stdin.end();
  });

const writeSource = async (directory, language, code) => {
  const entryPoint = language.entryPoint || "Main";
  const sourcePath = path.join(
    directory,
    `${entryPoint}${language.extension}`
  );

  await fs.writeFile(sourcePath, code, "utf8");

  return sourcePath;
};

const compileSource = async (directory, sourcePath, language) => {
  if (!language.compiler) {
    return {
      stdout: "",
      stderr: "",
      exitCode: 0,
    };
  }

  let args;

  if (language.id === "java") {
    args = [
      "-encoding",
      "UTF-8",
      "-d",
      directory,
      sourcePath,
    ];
  } else if (language.id === "c" || language.id === "cpp") {
    args = [
      sourcePath,
      "-O2",
      "-o",
      path.join(directory, getExecutableName()),
    ];
  } else if (language.id === "kotlin") {
    args = [
      sourcePath,
      "-include-runtime",
      "-d",
      path.join(directory, "program.jar"),
    ];
  } else {
    args = [
      ...(language.compilerArgs || []),
      sourcePath,
    ];
  }

  return runProcess(
    language.compiler,
    args,
    { cwd: directory },
    COMPILATION_TIMEOUT_MS
  );
};

const runtimeCommand = (directory, language) => {
  if (language.id === "java") {
    return {
      command: language.runtime,
      args: [
        "-cp",
        directory,
        language.entryPoint || "Main",
      ],
    };
  }

  if (language.id === "c" || language.id === "cpp") {
    return {
      command: path.join(directory, getExecutableName()),
      args: [],
    };
  }

  if (language.id === "kotlin") {
    return {
      command: language.runtime,
      args: [
        "-jar",
        path.join(directory, "program.jar"),
      ],
    };
  }

  return {
    command: language.runtime,
    args: [
      ...(language.runtimeArgs || []),
      path.join(
        directory,
        `${language.entryPoint || "Main"}${language.extension}`
      ),
    ],
  };
};

export const executeCode = async (code, languageId, input = "") => {
  const language = getLanguage(languageId);

  if (!language) {
    return {
      stdout: "",
      stderr: `Unsupported language: ${languageId}`,
      compile_output: "",
      status: STATUS.INTERNAL_ERROR,
    };
  }

  if (!language.available) {
    return {
      stdout: "",
      stderr: `${language.name} compiler/runtime is not available on the server`,
      compile_output: "",
      status: STATUS.INTERNAL_ERROR,
    };
  }

  let directory;

  try {
    directory = await fs.mkdtemp(
      path.join(os.tmpdir(), "coding-run-")
    );

    const sourcePath = await writeSource(
      directory,
      language,
      code
    );

    const compilation = await compileSource(
      directory,
      sourcePath,
      language
    );

    if (compilation.timedOut) {
      return {
        stdout: compilation.stdout,
        stderr: compilation.stderr,
        compile_output: compilation.stderr,
        status: STATUS.TIME_LIMIT,
      };
    }

    if (compilation.spawnError) {
      return {
        stdout: compilation.stdout,
        stderr: compilation.stderr,
        compile_output: compilation.stderr,
        status: STATUS.INTERNAL_ERROR,
      };
    }

    if (compilation.exitCode !== 0) {
      return {
        stdout: compilation.stdout,
        stderr: compilation.stderr,
        compile_output: compilation.stderr,
        status: STATUS.COMPILATION_ERROR,
      };
    }

    const runtime = runtimeCommand(directory, language);

    const execution = await runProcess(
      runtime.command,
      runtime.args,
      { cwd: directory },
      EXECUTION_TIMEOUT_MS,
      input
    );

    if (execution.timedOut) {
      return {
        stdout: execution.stdout,
        stderr: execution.stderr,
        compile_output: "",
        status: STATUS.TIME_LIMIT,
      };
    }

    if (execution.spawnError) {
      return {
        stdout: execution.stdout,
        stderr: execution.stderr,
        compile_output: "",
        status: STATUS.INTERNAL_ERROR,
      };
    }

    if (execution.exitCode !== 0) {
      return {
        stdout: execution.stdout,
        stderr: execution.stderr,
        compile_output: "",
        status: STATUS.RUNTIME_ERROR,
      };
    }

    return {
      stdout: execution.stdout,
      stderr: execution.stderr,
      compile_output: "",
      status: STATUS.ACCEPTED,
    };
  } catch (error) {
    return {
      stdout: "",
      stderr: error.message,
      compile_output: "",
      status: STATUS.INTERNAL_ERROR,
    };
  } finally {
    if (directory) {
      await fs
        .rm(directory, {
          recursive: true,
          force: true,
        })
        .catch(() => {});
    }
  }
};

const clean = (value) =>
  String(value ?? "").replace(/\r/g, "").trim();

const normalize = (value) =>
  clean(value).replace(/\s+/g, "");

export const runTestCases = async (
  code,
  languageId,
  testCases = []
) => {
  const results = [];

  for (const testCase of testCases) {
    const input = String(testCase?.input ?? "");

    const expected = String(
      testCase?.expected ?? testCase?.output ?? ""
    );

    const execution = await executeCode(
      code,
      languageId,
      input
    );

    const statusDescription =
      execution.status.description;

    const isAccepted =
      execution.status.id === STATUS.ACCEPTED.id;

    const passed =
      isAccepted &&
      normalize(execution.stdout) === normalize(expected);

    results.push({
      input,
      expected: clean(expected),
      output:
        clean(execution.stdout) ||
        clean(execution.stderr),
      status: passed
        ? "AC"
        : isAccepted
          ? "WA"
          : statusDescription,
      passed,
    });
  }

  return results;
};