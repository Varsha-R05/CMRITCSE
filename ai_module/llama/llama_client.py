import os
import time
from typing import Optional

import ollama
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

if not OLLAMA_API_KEY:
    print("WARNING: OLLAMA_API_KEY is not configured")

ollama_client = ollama.Client(
    host="https://ollama.com",
    headers={
        "Authorization": f"Bearer {OLLAMA_API_KEY}"
    } if OLLAMA_API_KEY else {},
)


def ask_llama(
    prompt: str,
    max_tokens: int = 800,
    temperature: float = 0.5,
    response_format: Optional[str] = "json",
):
    try:
        if not OLLAMA_API_KEY:
            print("OLLAMA CLOUD ERROR: OLLAMA_API_KEY is missing")
            return None

        start_time = time.perf_counter()

        chat_options = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": max_tokens,
                "num_ctx": 4096,
            },
        }

        # Keep JSON format support, but allow normal text if disabled.
        if response_format:
            chat_options["format"] = response_format

        response = ollama_client.chat(**chat_options)

        print(
            "Ollama Cloud request duration:",
            round(time.perf_counter() - start_time, 2),
            "seconds",
        )

        print("Prompt tokens:", getattr(response, "prompt_eval_count", 0))
        print("Generated tokens:", getattr(response, "eval_count", 0))

        message = response.message
        content = message.content or ""
        thinking = getattr(message, "thinking", "") or ""

        print("Ollama finish reason:", getattr(response, "done_reason", "unknown"))
        print("Content length:", len(content))
        print("Thinking length:", len(thinking))
        print("Content preview:", repr(content[:500]))
        print("Thinking preview:", repr(thinking[:500]))

        if not content.strip():
            print("OLLAMA CLOUD ERROR: No final answer in content")
            return None

        return content.strip()

    except Exception as error:
        print("OLLAMA CLOUD ERROR:", repr(error))
        return None