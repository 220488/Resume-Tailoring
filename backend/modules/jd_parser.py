"""
Person 2 — Job Description Parsing

INPUT  (from frontend via main.py):
    jd_text: str  — raw job description text pasted by the user

OUTPUT (passed directly to alignment.py as a string):
    A JSON string matching the schema below.

Output JSON schema:
{
    "job_title": str,
    "required_skills": [
        { "name": str, "category": "technical" | "domain" | "soft" }
    ],
    "preferred_skills": [
        { "name": str, "category": "technical" | "domain" | "soft" }
    ],
    "role_keywords": [str],
    "responsibilities": [str],
    "experience": {
        "level": "entry" | "junior" | "mid" | "senior" | "not_specified",
        "years_min": int | null,
        "years_max": int | null,
        "education": str | null
    }
}

category definitions:
    "technical" — programming languages, frameworks, tools, platforms (e.g. Python, Docker, AWS)
    "domain"    — subject-matter knowledge areas (e.g. machine learning, data pipelines, NLP)
    "soft"      — interpersonal / workplace skills (e.g. communication, teamwork, leadership)
"""

import json

from backend.llm_client import call_llm

SYSTEM_PROMPT = """
You are a job description parser. Your task is to extract structured information from a job posting and return it as valid JSON.

Skill classification rules:
- "required": skills listed under "Required", "Must have", "Essential", "Qualifications", or described as mandatory.
- "preferred": skills listed under "Preferred", "Nice to have", "Bonus", "Plus", or described as optional.
- When unclear, default to "required".

Skill category definitions:
- "technical": programming languages, frameworks, tools, platforms (e.g. Python, Docker, AWS, React)
- "domain": subject-matter knowledge areas (e.g. machine learning, data pipelines, NLP, finance)
- "soft": interpersonal or workplace skills (e.g. communication, teamwork, leadership, problem-solving)

Experience level mapping:
- "entry": 0–1 years or explicitly entry-level / new grad
- "junior": 1–3 years
- "mid": 3–5 years
- "senior": 5+ years or explicitly senior/lead/principal
- "not_specified": no experience level mentioned

Return ONLY valid JSON that matches this exact schema — no explanation, no markdown, no code fences:

{
    "job_title": "<string>",
    "required_skills": [
        { "name": "<string>", "category": "technical" | "domain" | "soft" }
    ],
    "preferred_skills": [
        { "name": "<string>", "category": "technical" | "domain" | "soft" }
    ],
    "role_keywords": ["<string>"],
    "responsibilities": ["<string>"],
    "experience": {
        "level": "entry" | "junior" | "mid" | "senior" | "not_specified",
        "years_min": <int or null>,
        "years_max": <int or null>,
        "education": "<string or null>"
    }
}
"""


def _deduplicate_skills(skills: list) -> list:
    seen: set[str] = set()
    result = []
    for s in skills:
        name = s.get("name", "").strip().lower()
        if name and name not in seen:
            seen.add(name)
            result.append(s)
    return result


def _clean_output(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    data["required_skills"] = _deduplicate_skills(data.get("required_skills", []))
    data["preferred_skills"] = _deduplicate_skills(data.get("preferred_skills", []))
    data.setdefault("job_title", None)
    data.setdefault("role_keywords", [])
    data.setdefault("responsibilities", [])
    if not isinstance(data.get("experience"), dict):
        data["experience"] = {
            "level": "not_specified",
            "years_min": None,
            "years_max": None,
            "education": None,
        }
    return data


def parse_jd(jd_text: str) -> str:
    """
    Parse a job description and return structured JSON.

    Calls the LLM, then applies post-processing: skill deduplication,
    missing-key defaults, and experience block repair.

    Args:
        jd_text: Raw job description text.

    Returns:
        A JSON string matching the schema defined in this file's docstring.
        This string is passed directly to the Alignment Analyzer (Stage 3).
    """
    raw = call_llm(SYSTEM_PROMPT, jd_text)
    try:
        data = json.loads(raw)
        return json.dumps(_clean_output(data))
    except json.JSONDecodeError:
        return raw
