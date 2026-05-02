"""
Tailored Resume Generation / Prompt Design

This file is written as a standalone module.
It does NOT modify any teammate's files.

Input:
    jd_json:        str or dict
    resume_json:    str or dict
    alignment_json: str or dict

Output:
    generate_tailored_resume(...) returns a Python dict.
    generate_tailored_resume_json(...) returns a JSON string.

Output schema:
{
    "professional_summary": str,
    "reordered_skills": [str],
    "rewritten_bullets": [
        {
            "original": str,
            "revised": str,
            "rationale": str
        }
    ]
}

Main design principles:
1. Use Gemini API Free Tier when available.
2. Do not fabricate resume information.
3. Use only facts already present in the candidate resume.
4. Reorder existing skills only.
5. Rewrite up to three existing bullets only.
6. Validate LLM output to reduce unsupported claims.
7. Provide safe fallback output if the API fails.
"""

import os
import json
import re
from typing import Any, Dict, List, Union

from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# =========================================================
# 1. SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are a professional resume tailoring assistant.

You will receive three JSON objects:
1. JD: a parsed job description
2. RESUME: a parsed candidate resume
3. ALIGNMENT: an alignment report between the JD and the resume

Your task is to generate tailored resume content for the candidate.

Strict rules:
1. Use ONLY information that already exists in the candidate resume.
2. Do NOT invent skills, tools, certifications, companies, dates, achievements, metrics, projects, or responsibilities.
3. Do NOT add missing skills into the candidate's resume.
4. You may rephrase, reorganise, and emphasise existing resume content.
5. Rewritten bullets must preserve the factual meaning of the original bullet.
6. Prefer bullets from ALIGNMENT.weak_matches.
7. If fewer than three weak matches exist, use relevant bullets from work_experience or projects.
8. Return up to three rewritten bullets only.
9. Return valid JSON only.

The final output must follow this exact schema:

{
  "professional_summary": "string",
  "reordered_skills": ["string"],
  "rewritten_bullets": [
    {
      "original": "string",
      "revised": "string",
      "rationale": "string"
    }
  ]
}

Field requirements:
- professional_summary:
  Write 3–4 concise sentences tailored to the target role.
  It must be based only on the resume content.

- reordered_skills:
  Use only skills that already exist in the candidate resume.
  Put JD-matched skills first.

- rewritten_bullets:
  Rewrite up to three original bullets.
  The original field must copy the original bullet exactly.
  The revised field must improve wording for JD relevance without adding new facts.
  The rationale field must briefly explain the change.
"""


# =========================================================
# 2. JSON HELPERS
# =========================================================

def safe_json_loads(data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert a JSON string to a Python dictionary.
    If the input is already a dictionary, return it.
    """
    if isinstance(data, dict):
        return data

    if isinstance(data, str):
        try:
            loaded = json.loads(data)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}

    return {}


def normalise(text: str) -> str:
    """
    Lowercase and strip text for safer comparison.
    """
    if not isinstance(text, str):
        return ""
    return text.strip().lower()


def is_empty_resume(resume: Dict[str, Any]) -> bool:
    """
    Detect whether resume_parser returned an empty fallback structure.
    """
    if not isinstance(resume, dict):
        return True

    return (
        not resume.get("skills")
        and not resume.get("education")
        and not resume.get("work_experience")
        and not resume.get("projects")
    )


def extract_resume_skills(resume: Dict[str, Any]) -> List[str]:
    """
    Extract original skills from the parsed resume.

    Expected schema:
    "skills": [
        {"name": "Python", "category": "technical"}
    ]

    Also supports:
    "skills": ["Python", "SQL"]
    """
    skills = []

    for skill in resume.get("skills", []):
        if isinstance(skill, dict):
            name = skill.get("name")
            if name:
                skills.append(str(name).strip())
        elif isinstance(skill, str):
            skills.append(skill.strip())

    seen = set()
    unique_skills = []

    for skill in skills:
        key = normalise(skill)
        if key and key not in seen:
            seen.add(key)
            unique_skills.append(skill)

    return unique_skills


def extract_matched_items(alignment: Dict[str, Any]) -> List[str]:
    """
    Extract matched items from the alignment report.
    """
    matched = []

    for item in alignment.get("matched", []):
        if isinstance(item, dict) and item.get("item"):
            matched.append(str(item["item"]).strip())
        elif isinstance(item, str):
            matched.append(item.strip())

    return matched


def extract_jd_items(jd: Dict[str, Any]) -> List[str]:
    """
    Extract useful matching terms directly from the job description.
    This makes skill ordering more robust when the alignment report is incomplete.
    """
    items = []

    for section in ["required_skills", "preferred_skills"]:
        for skill in jd.get(section, []):
            if isinstance(skill, dict) and skill.get("name"):
                items.append(str(skill["name"]).strip())
            elif isinstance(skill, str):
                items.append(skill.strip())

    for keyword in jd.get("role_keywords", []):
        if isinstance(keyword, str):
            items.append(keyword.strip())

    for responsibility in jd.get("responsibilities", []):
        if isinstance(responsibility, str):
            items.append(responsibility.strip())

    experience = jd.get("experience", {})
    if isinstance(experience, dict):
        education = experience.get("education")
        if isinstance(education, str):
            items.append(education.strip())

    seen = set()
    unique_items = []

    for item in items:
        key = normalise(item)
        if key and key not in seen:
            seen.add(key)
            unique_items.append(item)

    return unique_items


def collect_resume_bullets(resume: Dict[str, Any]) -> List[str]:
    """
    Collect original bullet text from work experience and projects.
    """
    bullets = []

    for job in resume.get("work_experience", []):
        if not isinstance(job, dict):
            continue

        for bullet in job.get("bullets", []):
            if isinstance(bullet, dict) and bullet.get("text"):
                bullets.append(str(bullet["text"]).strip())
            elif isinstance(bullet, str):
                bullets.append(bullet.strip())

    for project in resume.get("projects", []):
        if not isinstance(project, dict):
            continue

        for bullet in project.get("bullets", []):
            if isinstance(bullet, dict) and bullet.get("text"):
                bullets.append(str(bullet["text"]).strip())
            elif isinstance(bullet, str):
                bullets.append(bullet.strip())

    seen = set()
    unique_bullets = []

    for bullet in bullets:
        key = normalise(bullet)
        if key and key not in seen:
            seen.add(key)
            unique_bullets.append(bullet)

    return unique_bullets


def collect_resume_terms(resume: Dict[str, Any]) -> List[str]:
    """
    Collect grounded terms from the resume.
    These terms are used to construct safer fallback summaries.
    """
    terms = []

    terms.extend(extract_resume_skills(resume))

    for edu in resume.get("education", []):
        if not isinstance(edu, dict):
            continue

        degree = edu.get("degree")
        if degree:
            terms.append(str(degree).strip())

        for course in edu.get("relevant_coursework", []):
            if isinstance(course, str):
                terms.append(course.strip())

    for job in resume.get("work_experience", []):
        if isinstance(job, dict) and job.get("title"):
            terms.append(str(job["title"]).strip())

    for project in resume.get("projects", []):
        if not isinstance(project, dict):
            continue

        name = project.get("name")
        if name:
            terms.append(str(name).strip())

        for tech in project.get("technologies", []):
            if isinstance(tech, str):
                terms.append(tech.strip())

    seen = set()
    unique_terms = []

    for term in terms:
        key = normalise(term)
        if key and key not in seen:
            seen.add(key)
            unique_terms.append(term)

    return unique_terms


# =========================================================
# 3. RULE-BASED SAFETY FUNCTIONS
# =========================================================

UNSUPPORTED_PATTERNS = [
    r"\b\d+%",
    r"\b\d+\s*percent",
    r"\b\d+x\b",
    r"\b\d+\+\b",
    r"\bimproved by\b",
    r"\bincreased by\b",
    r"\bdecreased by\b",
    r"\breduced by\b",
    r"\bsaved\b",
    r"\bgenerated revenue\b",
    r"\bled a team\b",
    r"\bmanaged a team\b",
    r"\bowned\b",
    r"\bdelivered\b",
    r"\bautomated\b",
    r"\boptimised\b",
    r"\boptimized\b"
]


def contains_risky_claim(text: str) -> bool:
    """
    Detect potentially unsupported claims in revised bullets.
    This is intentionally conservative.
    """
    if not isinstance(text, str):
        return False

    text_lower = text.lower()

    return any(
        re.search(pattern, text_lower)
        for pattern in UNSUPPORTED_PATTERNS
    )


def adds_risky_claim(original: str, revised: str) -> bool:
    """
    Return True if the revised bullet contains risky claims
    that were not already present in the original bullet.
    """
    original_has_risk = contains_risky_claim(original)
    revised_has_risk = contains_risky_claim(revised)

    return revised_has_risk and not original_has_risk


def reorder_skills_safely(
    jd: Dict[str, Any],
    resume: Dict[str, Any],
    alignment: Dict[str, Any]
) -> List[str]:
    """
    Reorder only original resume skills.
    Skills matched to the JD appear first.
    This function never adds new skills.
    """
    original_skills = extract_resume_skills(resume)

    matching_terms = (
        extract_matched_items(alignment)
        + extract_jd_items(jd)
    )

    matching_norm = [normalise(item) for item in matching_terms]

    first = []
    rest = []

    for skill in original_skills:
        skill_norm = normalise(skill)

        is_matched = any(
            skill_norm == item
            or skill_norm in item
            or item in skill_norm
            for item in matching_norm
            if item
        )

        if is_matched:
            first.append(skill)
        else:
            rest.append(skill)

    return first + rest


def rewrite_bullet_safely(original: str, requirement: str) -> str:
    """
    Rule-based bullet rewrite for fallback mode.
    Improves wording without adding unsupported facts.
    """
    if not isinstance(original, str):
        return ""

    if not isinstance(requirement, str):
        requirement = ""

    requirement_lower = requirement.lower()
    original_lower = original.lower()

    # Specific safe rewrites for common resume evidence
    if "summary tables and charts" in original_lower:
        return (
            "Prepared summary tables and charts to support internal presentations "
            "and communicate data insights clearly."
        )

    if "tableau dashboard" in original_lower:
        return (
            "Created charts and a Tableau dashboard to present trends "
            "and communicate insights clearly."
        )

    if "cleaning and organising internal datasets" in original_lower:
        return (
            "Assisted with cleaning and organising internal datasets "
            "for weekly reporting and analysis tasks."
        )

    clean_original = original.strip().rstrip(".")

    # General communication / insight rule
    if (
        "communicate" in requirement_lower
        or "stakeholder" in requirement_lower
        or "insight" in requirement_lower
        or "presentation" in requirement_lower
    ):
        if (
            "chart" in original_lower
            or "presentation" in original_lower
            or "report" in original_lower
            or "summary" in original_lower
            or "finding" in original_lower
        ):
            return (
                clean_original
                + " to support clear data insight communication."
            )

    # General dashboard rule
    if "dashboard" in requirement_lower or "visual" in requirement_lower:
        if (
            "tableau" in original_lower
            or "dashboard" in original_lower
            or "chart" in original_lower
        ):
            return (
                clean_original
                + " to support dashboard reporting and trend communication."
            )

    # General data analysis rule
    if (
        "analyse" in requirement_lower
        or "analyze" in requirement_lower
        or "analysis" in requirement_lower
        or "dataset" in requirement_lower
    ):
        if (
            "data" in original_lower
            or "python" in original_lower
            or "sql" in original_lower
            or "analysis" in original_lower
            or "analysed" in original_lower
            or "analyzed" in original_lower
        ):
            return (
                clean_original
                + " to support data analysis and evidence-based reporting."
            )

    return original.strip()


def build_safe_professional_summary(
    jd: Dict[str, Any],
    resume: Dict[str, Any],
    alignment: Dict[str, Any],
    reordered_skills: List[str]
) -> str:
    """
    Build a fallback professional summary using only grounded resume information.
    """
    candidate_name = resume.get("candidate_name") or "The candidate"
    job_title = jd.get("job_title") or "the target role"

    if is_empty_resume(resume):
        return (
            f"{candidate_name} is a candidate for {job_title}. "
            "The resume parser did not return enough structured information to generate "
            "a detailed tailored summary without risking unsupported claims."
        )

    resume_terms = collect_resume_terms(resume)
    matched_items = extract_matched_items(alignment)

    grounded_matches = []

    for item in matched_items:
        item_norm = normalise(item)

        for term in resume_terms:
            term_norm = normalise(term)

            if item_norm == term_norm or item_norm in term_norm or term_norm in item_norm:
                grounded_matches.append(term)
                break

    if not grounded_matches:
        grounded_matches = reordered_skills[:5]

    seen = set()
    grounded_matches_unique = []

    for item in grounded_matches:
        key = normalise(item)
        if key and key not in seen:
            seen.add(key)
            grounded_matches_unique.append(item)

    if grounded_matches_unique:
        evidence = ", ".join(grounded_matches_unique[:5])
        evidence_sentence = (
            f"The candidate's background includes experience with {evidence}."
        )
    else:
        evidence_sentence = (
            "The candidate's background includes academic and applied experience relevant to the target role."
        )

    education = resume.get("education", [])
    education_sentence = ""

    if education and isinstance(education[0], dict):
        degree = education[0].get("degree")
        institution = education[0].get("institution")

        if degree and institution:
            education_sentence = (
                f"The candidate is pursuing a {degree} "
                f"at {institution}."
            )
        elif degree:
            education_sentence = f"The candidate is associated with {degree}."

    bullets = collect_resume_bullets(resume)

    if bullets:
        application_sentence = (
            "The resume provides evidence of practical experience through work or project-based bullet points."
        )
    else:
        application_sentence = (
            "The profile is positioned toward applying data-related skills to practical tasks."
        )

    summary_parts = [
        f"{candidate_name} is a data science candidate with experience relevant to {job_title}.",
        evidence_sentence
    ]

    if education_sentence:
        summary_parts.append(education_sentence)

    summary_parts.append(application_sentence)

    return " ".join(summary_parts)


def fallback_tailored_resume(
    jd: Dict[str, Any],
    resume: Dict[str, Any],
    alignment: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Safe fallback output used when the API fails or returns invalid JSON.
    This keeps the module usable for demos without fabricating information.
    """
    reordered_skills = reorder_skills_safely(jd, resume, alignment)

    professional_summary = build_safe_professional_summary(
        jd=jd,
        resume=resume,
        alignment=alignment,
        reordered_skills=reordered_skills
    )

    rewritten_bullets = []

    # Prefer weak matches from alignment.py
    for weak in alignment.get("weak_matches", []):
        if len(rewritten_bullets) >= 3:
            break

        if not isinstance(weak, dict):
            continue

        original = weak.get("resume_bullet")
        requirement = weak.get("jd_requirement")

        if original:
            revised = rewrite_bullet_safely(original, requirement or "")

            if adds_risky_claim(original, revised):
                revised = original
                rationale = (
                    "The original bullet was retained because the revised version "
                    "may introduce unsupported claims."
                )
            elif revised == original:
                rationale = (
                    "The original bullet was retained because it already provides "
                    "relevant resume evidence."
                )
            else:
                rationale = (
                    "The bullet was reframed to emphasise its relevance to the job description "
                    "while preserving the original meaning."
                )

            rewritten_bullets.append({
                "original": original,
                "revised": revised,
                "rationale": rationale
            })

    # If not enough weak matches, use existing resume bullets
    if len(rewritten_bullets) < 3:
        existing_originals = {item["original"] for item in rewritten_bullets}

        for bullet in collect_resume_bullets(resume):
            if len(rewritten_bullets) >= 3:
                break

            if bullet not in existing_originals:
                rewritten_bullets.append({
                    "original": bullet,
                    "revised": bullet,
                    "rationale": (
                        "The original bullet was retained because it already provides "
                        "relevant resume evidence."
                    )
                })

    return {
        "professional_summary": professional_summary,
        "reordered_skills": reordered_skills,
        "rewritten_bullets": rewritten_bullets
    }


def validate_output(
    output: Dict[str, Any],
    jd: Dict[str, Any],
    resume: Dict[str, Any],
    alignment: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate and clean the LLM output.
    This prevents unsupported skills, unsupported original bullets,
    and risky revised bullet claims.
    """
    if not isinstance(output, dict):
        return fallback_tailored_resume(jd, resume, alignment)

    fallback = fallback_tailored_resume(jd, resume, alignment)
    cleaned = {}

    # 1. professional_summary
    summary = output.get("professional_summary")

    if isinstance(summary, str) and summary.strip() and not is_empty_resume(resume):
        cleaned["professional_summary"] = summary.strip()
    else:
        cleaned["professional_summary"] = fallback["professional_summary"]

    # 2. reordered_skills: keep only original resume skills
    original_skills = extract_resume_skills(resume)
    original_norm_map = {
        normalise(skill): skill for skill in original_skills
    }

    cleaned_skills = []

    if isinstance(output.get("reordered_skills"), list):
        for skill in output["reordered_skills"]:
            if not isinstance(skill, str):
                continue

            key = normalise(skill)

            if key in original_norm_map:
                original_skill = original_norm_map[key]

                if original_skill not in cleaned_skills:
                    cleaned_skills.append(original_skill)

    # Add any original skills not returned by the LLM
    for skill in original_skills:
        if skill not in cleaned_skills:
            cleaned_skills.append(skill)

    if cleaned_skills:
        cleaned["reordered_skills"] = cleaned_skills
    else:
        cleaned["reordered_skills"] = fallback["reordered_skills"]

    # 3. rewritten_bullets: original must be grounded in resume or weak_matches
    valid_originals = set(collect_resume_bullets(resume))

    for weak in alignment.get("weak_matches", []):
        if isinstance(weak, dict) and weak.get("resume_bullet"):
            valid_originals.add(weak["resume_bullet"])

    cleaned_bullets = []

    if isinstance(output.get("rewritten_bullets"), list):
        for item in output["rewritten_bullets"]:
            if len(cleaned_bullets) >= 3:
                break

            if not isinstance(item, dict):
                continue

            original = item.get("original")
            revised = item.get("revised")
            rationale = item.get("rationale")

            if not all(isinstance(x, str) for x in [original, revised, rationale]):
                continue

            original = original.strip()
            revised = revised.strip()
            rationale = rationale.strip()

            if original not in valid_originals:
                continue

            # Prevent revised bullet from adding unsupported quantitative or achievement claims
            if adds_risky_claim(original, revised):
                revised = original
                rationale = (
                    "The original bullet was retained because the revised version "
                    "may introduce unsupported claims."
                )

            cleaned_bullets.append({
                "original": original,
                "revised": revised,
                "rationale": rationale
            })

    if not cleaned_bullets:
        cleaned_bullets = fallback["rewritten_bullets"]

    cleaned["rewritten_bullets"] = cleaned_bullets[:3]

    return cleaned


# =========================================================
# 4. GEMINI API CALL
# =========================================================

def call_gemini_json(prompt: str, model_name: str = "gemini-2.5-flash") -> Dict[str, Any]:
    """
    Call Gemini API and ask for JSON output.

    Required .env format:
        GEMINI_API_KEY=your_api_key_here
    """
    if genai is None or types is None:
        raise ImportError(
            "google-genai is not installed. Install it or run with use_api=False."
        )

    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. "
            "Create a .env file and add GEMINI_API_KEY=your_api_key_here"
        )

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json"
        )
    )

    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return {}


# =========================================================
# 5. MAIN FUNCTIONS FOR PERSON 5
# =========================================================

def generate_tailored_resume(
    jd_json: Union[str, Dict[str, Any]],
    resume_json: Union[str, Dict[str, Any]],
    alignment_json: Union[str, Dict[str, Any]],
    use_api: bool = True
) -> Dict[str, Any]:
    """
    Generate tailored resume content as a Python dictionary.

    This function accepts either JSON strings or dictionaries, so it can receive
    outputs from jd_parsing.py, resume_parser.py, and alignment.py.
    """
    jd = safe_json_loads(jd_json)
    resume = safe_json_loads(resume_json)
    alignment = safe_json_loads(alignment_json)

    user_prompt = f"""
{SYSTEM_PROMPT}

====================
JD JSON
====================
{json.dumps(jd, indent=2)}

====================
RESUME JSON
====================
{json.dumps(resume, indent=2)}

====================
ALIGNMENT JSON
====================
{json.dumps(alignment, indent=2)}
"""

    if use_api:
        try:
            raw_output = call_gemini_json(user_prompt)
        except Exception as error:
            print(f"[Warning] Gemini API call failed: {error}")
            raw_output = fallback_tailored_resume(jd, resume, alignment)
    else:
        raw_output = fallback_tailored_resume(jd, resume, alignment)

    cleaned_output = validate_output(
        output=raw_output,
        jd=jd,
        resume=resume,
        alignment=alignment
    )

    return cleaned_output


def generate_tailored_resume_json(
    jd_json: Union[str, Dict[str, Any]],
    resume_json: Union[str, Dict[str, Any]],
    alignment_json: Union[str, Dict[str, Any]],
    use_api: bool = True
) -> str:
    """
    Generate tailored resume content as a JSON string.

    This wrapper is recommended for main.py or frontend integration.
    """
    result = generate_tailored_resume(
        jd_json=jd_json,
        resume_json=resume_json,
        alignment_json=alignment_json,
        use_api=use_api
    )

    return json.dumps(result, indent=2, ensure_ascii=False)


__all__ = [
    "generate_tailored_resume",
    "generate_tailored_resume_json",
    "fallback_tailored_resume",
    "validate_output"
]