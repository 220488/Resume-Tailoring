"""
Person 5 — Tailored Resume Generation

INPUT  (from main.py):
    jd_json:        str  — JSON string from jd_parser.py      (Person 2)
    resume_json:    str  — JSON string from resume_parser.py   (Person 3)
    alignment_json: str  — JSON string from alignment.py       (Person 4)

OUTPUT (returned to the frontend as a string):
    A JSON string representing a complete tailored resume.

Output JSON schema:
{
    "candidate_name": str | null,
    "professional_summary": str,
    "skills": [str],                         -- reordered: JD-matched first
    "work_experience": [
        {
            "company": str,
            "title":   str,
            "start_date": str,
            "end_date":   str | null,
            "bullets":    [str]              -- tailored bullets
        }
    ],
    "education": [
        {
            "degree": str,
            "institution": str,
            "graduation_year": int | null,
            "gpa": float | null,
            "relevant_coursework": [str]
        }
    ],
    "projects": [
        {
            "name": str,
            "technologies": [str],
            "bullets": [str]                 -- tailored bullets
        }
    ]
}
"""

from backend.llm_client import call_llm

SYSTEM_PROMPT = """
You are an expert resume writer. You will receive three JSON inputs:
1. A parsed job description (JD)
2. A parsed resume — the candidate's source-of-truth facts
3. An alignment report (matched / missing / weak_matches)

Produce a single tailored resume as one JSON object.

Hard rules — follow strictly:
- Preserve EVERY fact in the parsed resume. Do NOT invent companies, titles, dates,
  technologies, education entries, GPAs, project names, or achievements that are
  not present in the parsed resume.
- Do NOT add bullets that are not grounded in the original resume content.
- The candidate's identity, education, dates, and project names must be carried over verbatim.
- The "missing" items in the alignment report describe gaps. Do NOT fabricate experience
  to fill them.

Per-section rules:

professional_summary
- 3–4 sentences in third-person professional voice (no "I", no "we").
- Highlight the candidate's most relevant experience for the JD's job title.
- Naturally incorporate 2–3 role keywords from the JD.
- Base ONLY on what the resume contains.

skills
- Flat list of skill name strings (no objects, no categories).
- Source from the candidate's resume skills only.
- Reorder: skills matching JD required_skills first → matching preferred_skills next → remaining skills last.
- Do NOT add skills not present in the candidate's resume.

work_experience
- Keep every role from the resume, in the same order.
- Preserve company, title, start_date, end_date verbatim.
- For each bullet:
    * If the bullet appears in alignment.weak_matches OR is closely related to a JD requirement:
      rewrite it to better reflect JD keywords. Start with a strong past-tense action verb.
      Preserve any numbers, metrics, and concrete outcomes from the original.
    * Otherwise keep wording close to the original, optionally tightening for clarity.
    * Never introduce new tools, technologies, scope, or achievements not in the original bullet.
- "bullets" is a flat list of strings (no objects, no rationale).

education
- Copy education entries verbatim from the resume. No rewriting.

projects
- Keep every project. Preserve name and technologies verbatim.
- Bullets follow the same rewriting rules as work_experience.

Return ONLY valid JSON — no markdown fences, no explanation. Use exactly this schema:
{
    "candidate_name": string | null,
    "professional_summary": string,
    "skills": [string],
    "work_experience": [
        {
            "company": string,
            "title": string,
            "start_date": string,
            "end_date": string | null,
            "bullets": [string]
        }
    ],
    "education": [
        {
            "degree": string,
            "institution": string,
            "graduation_year": integer | null,
            "gpa": number | null,
            "relevant_coursework": [string]
        }
    ],
    "projects": [
        {
            "name": string,
            "technologies": [string],
            "bullets": [string]
        }
    ]
}
"""


def generate_tailored_resume(jd_json: str, resume_json: str, alignment_json: str) -> str:
    """
    Generate a complete tailored resume based on the JD, resume, and alignment report.

    Args:
        jd_json:        Raw JSON string from parse_jd()          (Stage 1).
        resume_json:    Raw JSON string from parse_resume()      (Stage 2).
        alignment_json: Raw JSON string from analyze_alignment() (Stage 3).

    Returns:
        A JSON string matching the schema defined in this file's docstring.
        This is the final output sent to the frontend.
    """
    user_content = (
        f"JD:\n{jd_json}\n\n"
        f"RESUME:\n{resume_json}\n\n"
        f"ALIGNMENT:\n{alignment_json}"
    )
    return call_llm(SYSTEM_PROMPT, user_content, max_tokens=8192)
