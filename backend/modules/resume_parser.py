"""
Person 3 — Resume Parsing

INPUT  (from main.py, after PDF text extraction):
    resume_text: str  — plain text extracted from the uploaded PDF

OUTPUT (passed directly to alignment.py as a string):
    A JSON string matching the schema below.

Output JSON schema:
{
    "candidate_name": str | null,
    "skills": [
        { "name": str, "category": "technical" | "domain" | "soft" }
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
    "work_experience": [
        {
            "company": str,
            "title": str,
            "start_date": str,
            "end_date": str | null,
            "bullets": [
                {
                    "text": str,
                    "skills_mentioned": [str]
                }
            ]
        }
    ],
    "projects": [
        {
            "name": str,
            "technologies": [str],
            "bullets": [
                {
                    "text": str,
                    "skills_mentioned": [str]
                }
            ]
        }
    ]
}

Field notes:
    skills            — flat list from the resume's explicit skills / tech section
    bullets.text      — original bullet text, copied EXACTLY as written in the resume
    skills_mentioned  — skills the LLM detects are referenced inside that bullet
    end_date          — null if the role is current / present
"""

import json
import re
from typing import Any

from backend.llm_client import call_llm


SYSTEM_PROMPT = """
You are a strict resume parser.

You will receive resume text that may contain line-break noise from PDF/DOCX extraction.
Your task is to extract structured information and return ONLY valid JSON.

Hard rules (must follow):
1) Return ONLY valid JSON. No markdown, no comments, no extra text.
2) Use this exact schema and field names:
{
  "candidate_name": string | null,
  "skills": [
    { "name": string, "category": "technical" | "domain" | "soft" }
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
  "work_experience": [
    {
      "company": string,
      "title": string,
      "start_date": string,
      "end_date": string | null,
      "bullets": [
        { "text": string, "skills_mentioned": [string] }
      ]
    }
  ],
  "projects": [
    {
      "name": string,
      "technologies": [string],
      "bullets": [
        { "text": string, "skills_mentioned": [string] }
      ]
    }
  ]
}
3) bullets.text must copy the original resume bullet content exactly as written.
   - Do NOT paraphrase, rewrite, or merge bullets.
   - If a project or role description is a paragraph (not bullet format), store it as one bullet item.
4) skills must come ONLY from an explicit Skills/Technical Skills/Tech Stack section.
   - Do NOT infer new skills from work/project bullets into the skills list.
5) Do NOT fabricate any company, project, degree, date, technology, or achievement.
6) If information is missing, use null (for scalar fields) or [] (for arrays).
7) Skill category definitions:
   - technical: languages, frameworks, libraries, tools, cloud, databases, platforms
   - domain: knowledge areas (e.g., machine learning, NLP, data analysis, finance)
   - soft: communication, teamwork, leadership, collaboration, stakeholder management
8) For work experience end_date:
   - use null if role is current/present/now.
9) Keep extracted text concise and faithful to source formatting/content.
"""


SECTION_HEADINGS = {
    "skills",
    "technical skills",
    "core skills",
    "tech stack",
    "education",
    "work experience",
    "experience",
    "internship experience",
    "projects",
    "project experience",
}


def _normalize_bullets(text: str) -> str:
    return re.sub(r"[•●▪◦‣∙]", "-", text)


def _remove_page_break_noise(text: str) -> str:
    text = re.sub(r"\n?\s*--\s*\d+\s*of\s*\d+\s*--\s*\n?", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\f", "\n", text)
    return text


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _repair_broken_lines(text: str) -> str:
    lines = [ln.strip() for ln in text.split("\n")]
    merged: list[str] = []
    for line in lines:
        if not line:
            merged.append("")
            continue
        if not merged or not merged[-1]:
            merged.append(line)
            continue
        prev = merged[-1]
        is_heading = line.lower() in SECTION_HEADINGS or line.isupper()
        starts_new_item = bool(re.match(r"^(-|\*|\d+[\.\)])\s+", line))
        prev_ends_sentence = bool(re.search(r"[.:;!?]$", prev))
        if not is_heading and not starts_new_item and not prev_ends_sentence:
            merged[-1] = f"{prev} {line}"
        else:
            merged.append(line)
    return "\n".join(merged)


def clean_resume_text(resume_text: str) -> str:
    text = _normalize_bullets(resume_text)
    text = _remove_page_break_noise(text)
    text = _normalize_whitespace(text)
    text = _repair_broken_lines(text)
    return _normalize_whitespace(text)


def split_sections(clean_text: str) -> str:
    patterns = {
        "skills": r"(?im)^(technical skills|skills|core skills|tech stack)\s*$",
        "education": r"(?im)^(education)\s*$",
        "work_experience": r"(?im)^(work experience|experience|internship experience)\s*$",
        "projects": r"(?im)^(projects|project experience)\s*$",
    }
    section_spans: list[tuple[int, str]] = []
    for key, pattern in patterns.items():
        for match in re.finditer(pattern, clean_text):
            section_spans.append((match.start(), key))
    if not section_spans:
        return clean_text
    section_spans.sort(key=lambda x: x[0])
    chunks: list[str] = []
    for idx, (start, key) in enumerate(section_spans):
        end = section_spans[idx + 1][0] if idx + 1 < len(section_spans) else len(clean_text)
        payload = clean_text[start:end].strip()
        if payload:
            chunks.append(f"[SECTION:{key}]\n{payload}")
    return "\n\n".join(chunks) if chunks else clean_text


def _validate_schema(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    required_top = ["candidate_name", "skills", "education", "work_experience", "projects"]
    if any(key not in data for key in required_top):
        return False
    if not all(isinstance(data[key], list) for key in ["skills", "education", "work_experience", "projects"]):
        return False

    for skill in data["skills"]:
        if not isinstance(skill, dict):
            return False
        if set(skill.keys()) != {"name", "category"}:
            return False

    for education in data["education"]:
        if not isinstance(education, dict):
            return False
        required_education = {"degree", "institution", "graduation_year", "gpa", "relevant_coursework"}
        if not required_education.issubset(education.keys()):
            return False
        if not isinstance(education.get("relevant_coursework"), list):
            return False

    for role in data["work_experience"]:
        if not isinstance(role, dict):
            return False
        required_role = {"company", "title", "start_date", "end_date", "bullets"}
        if not required_role.issubset(role.keys()) or not isinstance(role.get("bullets"), list):
            return False
        for bullet in role["bullets"]:
            if not isinstance(bullet, dict):
                return False
            if not {"text", "skills_mentioned"}.issubset(bullet.keys()):
                return False
            if not isinstance(bullet.get("skills_mentioned"), list):
                return False

    for project in data["projects"]:
        if not isinstance(project, dict):
            return False
        required_project = {"name", "technologies", "bullets"}
        if not required_project.issubset(project.keys()):
            return False
        if not isinstance(project.get("technologies"), list) or not isinstance(project.get("bullets"), list):
            return False
        for bullet in project["bullets"]:
            if not isinstance(bullet, dict):
                return False
            if not {"text", "skills_mentioned"}.issubset(bullet.keys()):
                return False
            if not isinstance(bullet.get("skills_mentioned"), list):
                return False

    return True


def parse_resume(resume_text: str) -> str:
    cleaned_text = clean_resume_text(resume_text)
    section_view = split_sections(cleaned_text)

    user_content = (
        "Resume text:\n"
        f"{cleaned_text}\n\n"
        "Section-aware view (for extraction stability):\n"
        f"{section_view}"
    )

    llm_output = call_llm(SYSTEM_PROMPT, user_content)
    try:
        parsed = json.loads(llm_output)
        if _validate_schema(parsed):
            return llm_output
    except json.JSONDecodeError:
        pass

    retry_prompt = (
        f"{user_content}\n\n"
        "Your previous output was invalid or schema-incompatible. "
        "Return valid JSON using the exact schema and constraints."
    )
    retry_output = call_llm(SYSTEM_PROMPT, retry_prompt)
    try:
        parsed_retry = json.loads(retry_output)
        if _validate_schema(parsed_retry):
            return retry_output
    except json.JSONDecodeError:
        pass

    return json.dumps(
        {
            "candidate_name": None,
            "skills": [],
            "education": [],
            "work_experience": [],
            "projects": [],
        }
    )


__all__ = ["parse_resume", "clean_resume_text", "split_sections"]
