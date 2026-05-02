"""
Quick connectivity test for backend.llm_client.
Run:
    python test_llm_connection.py
"""

from backend.llm_client import call_llm


if __name__ == "__main__":
    output = call_llm(
        system_prompt="You are a strict JSON assistant.",
        user_content='Return exactly: {"status":"ok"}',
        max_tokens=50,
        temperature=0.0,
    )
    print(output)
