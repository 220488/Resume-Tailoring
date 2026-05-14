"""
Stage 2.5 — Semantic Embedding Alignment

Runs between resume_parser (Stage 2) and alignment analyzer (Stage 3).
Uses a pre-trained sentence-transformer model to compute cosine similarity
between JD skills/keywords and resume bullets, producing a scored pre-analysis
that the LLM alignment stage uses as grounded context.

INPUT:
    jd_json:     str  — JSON string from jd_parser.py     (Stage 1)
    resume_json: str  — JSON string from resume_parser.py (Stage 2)

OUTPUT:
    A JSON string matching the schema below.

Output JSON schema:
{
    "similarity_scores": [
        {
            "jd_skill":   str,
            "jd_source":  "required_skills" | "preferred_skills" | "role_keywords",
            "best_bullet": str,
            "score":      float,   -- cosine similarity in [0, 1]
            "label":      "matched" | "weak_match" | "missing"
        }
    ],
    "overall_match_score": float   -- fraction of jd items labelled "matched"
}

Thresholds:
    score >= 0.75  →  "matched"
    score >= 0.45  →  "weak_match"
    score <  0.45  →  "missing"
"""

import json

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

MATCHED_THRESHOLD    = 0.75
WEAK_MATCH_THRESHOLD = 0.45

# Lazy-load the model once per process
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def compute_embedding_alignment(jd_json: str, resume_json: str) -> str:
    """
    Compute semantic similarity between JD skills/keywords and resume bullets.

    Args:
        jd_json:     Raw JSON string from parse_jd()     (Stage 1).
        resume_json: Raw JSON string from parse_resume() (Stage 2).

    Returns:
        A JSON string with per-skill similarity scores and labels.
        Passed to analyze_alignment() as additional context (Stage 3).
    """
    empty = json.dumps({"similarity_scores": [], "overall_match_score": 0.0})

    try:
        jd     = json.loads(jd_json)
        resume = json.loads(resume_json)
    except json.JSONDecodeError:
        return empty

    def _skill_name(item) -> str:
        # Accept dict {"name": ...} or plain string; ignore anything else
        if isinstance(item, dict):
            return str(item.get("name") or "").strip()
        if isinstance(item, str):
            return item.strip()
        return ""

    def _bullet_text(item) -> str:
        if isinstance(item, dict):
            return str(item.get("text") or "").strip()
        if isinstance(item, str):
            return item.strip()
        return ""

    # Collect JD items to score (required skills, preferred skills, role keywords)
    jd_items: list[dict] = []
    for skill in jd.get("required_skills") or []:
        text = _skill_name(skill)
        if text:
            jd_items.append({"text": text, "source": "required_skills"})
    for skill in jd.get("preferred_skills") or []:
        text = _skill_name(skill)
        if text:
            jd_items.append({"text": text, "source": "preferred_skills"})
    for kw in jd.get("role_keywords") or []:
        if isinstance(kw, str) and kw.strip():
            jd_items.append({"text": kw.strip(), "source": "role_keywords"})

    # Collect resume surface to match against (bullets + explicit skill names)
    resume_bullets: list[str] = []
    for job in resume.get("work_experience") or []:
        for bullet in (job or {}).get("bullets") or []:
            text = _bullet_text(bullet)
            if text:
                resume_bullets.append(text)
    for project in resume.get("projects") or []:
        for bullet in (project or {}).get("bullets") or []:
            text = _bullet_text(bullet)
            if text:
                resume_bullets.append(text)
    for skill in resume.get("skills") or []:
        text = _skill_name(skill)
        if text:
            resume_bullets.append(text)

    if not jd_items or not resume_bullets:
        return empty

    model = _get_model()

    jd_vecs     = model.encode([item["text"] for item in jd_items])
    bullet_vecs = model.encode(resume_bullets)

    # sim_matrix[i][j] = similarity between jd_items[i] and resume_bullets[j]
    sim_matrix = cosine_similarity(jd_vecs, bullet_vecs)

    results  = []
    n_matched = 0

    for i, item in enumerate(jd_items):
        best_idx   = int(np.argmax(sim_matrix[i]))
        best_score = float(sim_matrix[i][best_idx])

        if best_score >= MATCHED_THRESHOLD:
            label = "matched"
            n_matched += 1
        elif best_score >= WEAK_MATCH_THRESHOLD:
            label = "weak_match"
        else:
            label = "missing"

        results.append({
            "jd_skill":   item["text"],
            "jd_source":  item["source"],
            "best_bullet": resume_bullets[best_idx],
            "score":      round(best_score, 3),
            "label":      label,
        })

    overall_score = round(n_matched / len(jd_items), 3) if jd_items else 0.0

    return json.dumps({
        "similarity_scores":   results,
        "overall_match_score": overall_score,
    })
