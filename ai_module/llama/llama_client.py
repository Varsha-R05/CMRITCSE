
import os
import time
from typing import Optional

import ollama

MODEL_NAME = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

ollama_client = ollama.Client(
    host="https://ollama.com",
    headers={
        "Authorization": f"Bearer {OLLAMA_API_KEY}"
    },
)


def ask_llama(
    prompt: str,
    max_tokens: int = 200,
    temperature: float = 0.5,
    response_format: Optional[str] = "json",
):
    try:
        start_time = time.perf_counter()

        chat_options = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": max_tokens,
                "num_ctx": 4096,
            },
        }

        if response_format:
            chat_options["format"] = response_format

        response = ollama_client.chat(**chat_options)

        total_time = time.perf_counter() - start_time

        print("Ollama Cloud request duration:",
              round(total_time, 2), "seconds")
        print("Prompt tokens:", response.get("prompt_eval_count", 0))
        print("Generated tokens:", response.get("eval_count", 0))

        return response["message"]["content"]

    except Exception as error:
        print("OLLAMA CLOUD ERROR:", str(error))
        return None
