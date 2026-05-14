"""
Stage 3 — Alignment Analysis (LLM, grounded by embedding scores)

INPUT  (from main.py):
    jd_json:        str  — JSON string from jd_parser.py            (Stage 1)
    resume_json:    str  — JSON string from resume_parser.py        (Stage 2)
    embedding_json: str  — JSON string from embedding_matcher.py    (Stage 2.5)

OUTPUT (passed directly to generator.py as a string):
    A JSON string matching the schema below.

Output JSON schema:
{
    "matched": [
        {
            "item":   str,
            "source": "required_skills" | "preferred_skills" | "role_keywords" | "responsibilities"
        }
    ],
    "missing": [
        {
            "item":       str,
            "source":     "required_skills" | "preferred_skills" | "role_keywords" | "responsibilities",
            "importance": "high" | "medium" | "low"
        }
    ],
    "weak_matches": [
        {
            "jd_requirement": str,
            "resume_bullet":  str,
            "reason":         str
        }
    ]
}

Field notes:
    matched       — skill/keyword clearly present AND well-demonstrated in the resume
    missing       — required/preferred item absent or not addressable from the resume
    weak_matches  — resume has the experience but the bullet does not express it strongly
                    (e.g. skill listed in skills section but no bullet demonstrates it,
                     or bullet shows a related but not identical capability)
    importance    — high   = required_skills
                    medium = preferred_skills or role_keywords
                    low    = responsibilities only
"""

from backend.llm_client import call_llm

SYSTEM_PROMPT = """
You are a resume-JD alignment analyzer. You receive THREE inputs:

  1. JD                    — parsed job description (JSON)
  2. RESUME                — parsed resume (JSON)
  3. EMBEDDING PRE-ANALYSIS — cosine similarity scores between each JD skill/keyword
                              and the best-matching resume bullet, produced by a
                              sentence-transformer model (Stage 2.5)

How to use the embedding pre-analysis:
- It is quantitative evidence, not the final answer.
- Treat the pre-computed labels as a strong prior:
      score >= 0.75  → likely "matched"
      score >= 0.45  → likely "weak_match"
      score <  0.45  → likely "missing"
- You MAY override a label if the full textual context justifies it. Examples:
      * Upgrade weak_match → matched if a bullet clearly demonstrates the skill,
        even when the surface wording differs.
      * Downgrade matched → weak_match if the bullet only mentions the skill
        in passing (e.g. listed in a tools section but never used in a project).
      * Downgrade matched → missing if the high score reflects a coincidental
        word overlap rather than real evidence.
- When you override, your reasoning must be expressible in the "reason" field
  for weak_matches.

Definitions:
  matched       — skill or keyword clearly present AND demonstrated in the resume
  missing       — required/preferred item absent or not addressable
  weak_matches  — candidate has the underlying experience but the bullet does
                  not express it strongly enough for this JD

Importance levels for "missing":
  "high"   — from required_skills
  "medium" — from preferred_skills or role_keywords
  "low"    — from responsibilities only

Coverage rule:
- Every item in jd.required_skills, jd.preferred_skills, and jd.role_keywords must
  appear in exactly one of: matched, missing, or weak_matches.
- Do not invent items that are not in the JD.

Output rules:
- Return ONLY valid JSON. No markdown fences. No explanation outside the JSON.
- Use this exact schema:

{
    "matched": [
        {"item": string, "source": "required_skills"|"preferred_skills"|"role_keywords"|"responsibilities"}
    ],
    "missing": [
        {"item": string, "source": "required_skills"|"preferred_skills"|"role_keywords"|"responsibilities", "importance": "high"|"medium"|"low"}
    ],
    "weak_matches": [
        {"jd_requirement": string, "resume_bullet": string, "reason": string}
    ]
}
"""


def analyze_alignment(jd_json: str, resume_json: str, embedding_json: str) -> str:
    """
    Compare the parsed JD and resume using LLM reasoning grounded by embedding scores.

    Args:
        jd_json:        Raw JSON string from parse_jd()                  (Stage 1).
        resume_json:    Raw JSON string from parse_resume()              (Stage 2).
        embedding_json: Raw JSON string from compute_embedding_alignment (Stage 2.5).

    Returns:
        A JSON string matching the schema defined in this file's docstring.
        This string is passed directly to the Generator (Stage 4).
    """
    user_content = (
        f"JD:\n{jd_json}\n\n"
        f"RESUME:\n{resume_json}\n\n"
        f"EMBEDDING PRE-ANALYSIS (cosine similarity scores — use as evidence):\n{embedding_json}"
    )
    return call_llm(SYSTEM_PROMPT, user_content)
