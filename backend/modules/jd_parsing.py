"""
Job Description Parser Module (Person 2)

Hybrid JD parser:
- LLM extraction
- Rule-based validation + normalization
- Retry mechanism
- Robust cleaning (HD version)
"""

from backend.llm_client import call_llm
import json
import re
from typing import Any


# =========================================================
# SYSTEM PROMPT
# =========================================================
SYSTEM_PROMPT = """
You are a strict job description parser.

Extract structured information from a job description.

Rules:
1. Return ONLY valid JSON. No explanation.
2. Extract:
   - job_title
   - required_skills
   - preferred_skills
   - role_keywords
   - responsibilities
   - experience
3. Skill categories:
   - technical, domain, soft
4. Do NOT hallucinate.
5. Missing → [] or null

Return JSON only.
"""


# =========================================================
# SAFE JSON PARSING
# =========================================================
def _safe_json_load(raw_output: str):
    try:
        return json.loads(raw_output)
    except:
        match = re.search(r"\{.*\}", raw_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return {"error": "Invalid JSON", "raw_output": raw_output}


# =========================================================
# NORMALIZATION
# =========================================================
VALID_CATEGORIES = {"technical", "domain", "soft"}


def _normalize_skill_name(name: str):
    name = name.strip().lower()

    mapping = {
        "python programming": "python",
        "sql databases": "sql",
        "communication skills": "communication",
        "teamwork skills": "teamwork",
    }

    return mapping.get(name, name)


def _deduplicate_skills(skills):
    seen = set()
    cleaned = []

    if not isinstance(skills, list):
        return []

    for s in skills:
        raw_name = s.get("name", "")
        if not raw_name:
            continue  # 🔥 remove empty

        name = _normalize_skill_name(raw_name)

        category = s.get("category", "technical")
        if category not in VALID_CATEGORIES:
            category = "technical"  # 🔥 fix invalid category

        if name not in seen:
            seen.add(name)
            cleaned.append({
                "name": name,
                "category": category
            })

    return cleaned


def _normalize_experience(exp):
    if not isinstance(exp, dict):
        return {
            "level": "not_specified",
            "years_min": None,
            "years_max": None,
            "education": None
        }

    level_map = {
        "graduate": "entry",
        "intern": "entry",
        "entry-level": "entry",
        "junior": "junior",
        "mid-level": "mid",
        "senior": "senior"
    }

    level = exp.get("level", "not_specified")
    if isinstance(level, str):
        level = level_map.get(level.lower(), level)

    # 🔥 ensure numbers
    def safe_int(x):
        try:
            return int(x)
        except:
            return None

    return {
        "level": level,
        "years_min": safe_int(exp.get("years_min")),
        "years_max": safe_int(exp.get("years_max")),
        "education": exp.get("education")
    }


def _clean_text_list(lst):
    """Remove empty / noisy strings"""
    if not isinstance(lst, list):
        return []
    return [x.strip() for x in lst if isinstance(x, str) and x.strip()]


# =========================================================
# VALIDATION
# =========================================================
def _validate_schema(data: Any) -> bool:
    if not isinstance(data, dict):
        return False

    required_keys = [
        "job_title",
        "required_skills",
        "preferred_skills",
        "role_keywords",
        "responsibilities",
        "experience"
    ]

    if any(key not in data for key in required_keys):
        return False

    if not isinstance(data["required_skills"], list):
        return False
    if not isinstance(data["preferred_skills"], list):
        return False
    if not isinstance(data["role_keywords"], list):
        return False
    if not isinstance(data["responsibilities"], list):
        return False
    if not isinstance(data["experience"], dict):
        return False

    return True


# =========================================================
# CLEANING
# =========================================================
def _clean_output(data):
    if not isinstance(data, dict):
        return {"error": "Invalid structure", "raw": data}

    # Skills
    data["required_skills"] = _deduplicate_skills(data.get("required_skills", []))
    data["preferred_skills"] = _deduplicate_skills(data.get("preferred_skills", []))

    # Experience
    data["experience"] = _normalize_experience(data.get("experience"))

    # Text lists
    data["role_keywords"] = _clean_text_list(data.get("role_keywords"))
    data["responsibilities"] = _clean_text_list(data.get("responsibilities"))

    # Defaults
    data.setdefault("job_title", None)

    return data


# =========================================================
# MAIN FUNCTION
# =========================================================
def parse_jd(jd_text: str):

    # First attempt
    raw_output = call_llm(SYSTEM_PROMPT, jd_text)
    parsed = _safe_json_load(raw_output)

    if _validate_schema(parsed):
        return _clean_output(parsed)

    # Retry
    retry_prompt = (
        jd_text +
        "\n\nYour previous output was invalid. Return ONLY valid JSON."
    )

    retry_output = call_llm(SYSTEM_PROMPT, retry_prompt)
    parsed_retry = _safe_json_load(retry_output)

    return _clean_output(parsed_retry)