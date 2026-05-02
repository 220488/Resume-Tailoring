"""
This module provides a single entry point: call_llm(system_prompt, user_content).
All parser/alignment/generator modules depend on this function.
"""

import os
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()


def _get_env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def call_llm(
    system_prompt: str,
    user_content: str,
    max_tokens: int = 2048,
    temperature: float = 0.0,
) -> str:
    """
    Call OpenAI chat model and return plain text output.

    Notes:
    - Keep temperature low for deterministic parsing tasks.
    - Returns raw string so upstream modules can decide validation strategy.
    """
    api_key = _get_env("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned empty content.")
    return content.strip()

