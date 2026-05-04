"""Prototype validation for the Resume Tailoring Assistant.

This script verifies the backend contract, JSON structure, basic end-to-end API flow,
factual consistency of rewritten content, and alignment quality against a sample JD.
"""

import json
import os
import re
from pathlib import Path

import pdfplumber
import requests
from fpdf import FPDF

API_URL = os.getenv("API_URL", "http://localhost:8000")
SAMPLE_PDF_PATH = os.getenv("SAMPLE_PDF_PATH", "sample_data/sample_resume_jordan_chen.pdf")

# Run in Windows CMD:
# set API_URL=https://resume-tailor-backend-production-21b8.up.railway.app
# python tests\\test_prototype.py

# Run in PowerShell:
# $env:API_URL="https://resume-tailor-backend-production-21b8.up.railway.app"
# python tests/test_prototype.py


# A sample job description for testing purposes.
SAMPLE_JD = """
We are seeking a Junior Data Scientist to support predictive modelling and data-driven product decisions.
You will work with structured and unstructured data, develop machine learning solutions, and present findings clearly.

Required skills:
- Python
- SQL
- Machine learning
- Statistics
- Data preprocessing

Preferred skills:
- scikit-learn
- Pandas / NumPy
- Data visualisation
- Model evaluation
- Communication and teamwork

Qualifications:
- Bachelor or Master degree in data science, computer science, mathematics, or related field
- University projects or internship experience in machine learning is preferred
"""

REQUIRED_SKILLS = [
    "python",
    "sql",
    "machine learning",
    "statistics",
    "data preprocessing",
]

PLACEHOLDER_PATTERNS = [
    r"\[.*?\]",
    r"<.*?>",
    r"\bTBD\b",
    r"\bXXX\b",
    r"\bN/A\b",
    r"\byour company\b",
    r"\byour university\b",
]

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "will",
    "are", "you", "our", "their", "have", "has", "had", "been", "was", "were",
    "job", "role", "skills", "preferred", "required", "degree", "related",
    "support", "work", "using", "used", "data", "resume"
}


# Utility functions for testing and validation
def print_result(name: str, passed: bool, details: str = ""):
    icon = "PASS" if passed else "FAIL"
    print(f"[{icon}] {name}")
    if details:
        print(f"       {details}")


# Helper function to safely parse JSON fields that may be returned as strings or dicts.
def safe_json_load(value, field_name: str):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise AssertionError(f"{field_name} is not valid JSON: {e}")
    raise AssertionError(f"{field_name} must be a JSON string or dict, got {type(value)}")


# Extracts text from a PDF file using pdfplumber. Raises an error if the file is not found.
def extract_pdf_text(pdf_path: str) -> str:
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

    return "\n".join(text_parts).strip()


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Constructs the final tailored resume text based on the presence of full_resume_text or the preview fields.
def get_final_resume_text(tailored: dict) -> str:
    full_text = tailored.get("full_resume_text", "")
    if full_text and isinstance(full_text, str):
        return full_text.strip()

    summary = tailored.get("professional_summary", "")
    skills = tailored.get("reordered_skills", []) or tailored.get("skills", [])
    rewritten_bullets = tailored.get("rewritten_bullets", [])

    bullet_text = []
    for item in rewritten_bullets:
        revised = item.get("revised", "")
        if revised.strip():
            bullet_text.append(revised.strip())

    parts = [
        summary.strip(),
        " ".join(skills) if isinstance(skills, list) else str(skills),
        " ".join(bullet_text)
    ]
    return "\n".join([p for p in parts if p]).strip()


# Generates PDF bytes for export testing, based on the current frontend export logic.
def generate_pdf_bytes(tailored_data=None, full_text=None) -> bytes:
    """Generate PDF bytes for export testing, based on the current frontend export logic."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Tailored Resume", ln=True, align="C")
    pdf.ln(10)

    if full_text:
        pdf.set_font("Helvetica", "", 10)
        lines = full_text.split("\n")
        usable_width = pdf.w - pdf.l_margin - pdf.r_margin

        for line in lines:
            pdf.set_x(pdf.l_margin)
            if line.strip():
                pdf.multi_cell(usable_width, 5, line)
            else:
                pdf.ln(3)
    else:
        tailored_data = tailored_data or {}

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Professional Summary", ln=True)
        pdf.set_font("Helvetica", "", 10)
        summary = tailored_data.get("professional_summary", "")
        pdf.multi_cell(0, 5, summary)
        pdf.ln(5)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Skills", ln=True)
        pdf.set_font("Helvetica", "", 10)
        skills = tailored_data.get("reordered_skills", []) or tailored_data.get("skills", [])
        skills_text = " • ".join(skills) if skills else "—"
        pdf.multi_cell(0, 5, skills_text)
        pdf.ln(5)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Updated Achievements", ln=True)
        pdf.set_font("Helvetica", "", 10)
        bullets = tailored_data.get("rewritten_bullets", [])
        for i, bullet in enumerate(bullets, 1):
            revised = bullet.get("revised", "")
            if revised.strip():
                pdf.multi_cell(0, 5, f"{i}. {revised}")

    pdf_output = pdf.output(dest="S")
    if isinstance(pdf_output, str):
        return pdf_output.encode("latin-1")
    return bytes(pdf_output)


def build_export_outputs(tailored: dict) -> tuple[bytes, str, str]:
    """Build PDF, text, and JSON exports using the same branching as the frontend."""
    full_text = re.sub(r"\n{3,}", "\n\n", str(tailored.get("full_resume_text") or "").strip())

    pdf_bytes = generate_pdf_bytes(
        full_text=full_text if full_text else None,
        tailored_data=tailored if not full_text else None,
    )

    plain_text = full_text if full_text else f"""TAILORED RESUME

Professional Summary:
{tailored.get('professional_summary', '')}

Skills:
{chr(10).join('• ' + skill for skill in (tailored.get('reordered_skills', []) or tailored.get('skills', [])))}

Updated Achievements:
{chr(10).join('• ' + b.get('revised', '') for b in tailored.get('rewritten_bullets', []) if b.get('revised', '').strip())}
"""

    json_text = json.dumps(tailored, ensure_ascii=False, indent=2)
    return pdf_bytes, plain_text, json_text


# Sends a resume PDF and JD text to the /analyze endpoint and returns the response along with status code.
def analyze_resume(jd_text: str, pdf_path: str) -> dict:
    with open(pdf_path, "rb") as f:
        response = requests.post(
            f"{API_URL}/analyze",
            data={"jd_text": jd_text},
            files={"resume_pdf": (Path(pdf_path).name, f, "application/pdf")},
            timeout=300,
        )
    return {
        "status_code": response.status_code,
        "response": response,
    }


# Extracts 4-digit years from text and returns them as a set. Used to check for unsupported year fabrication.
def extract_years(text: str):
    return set(re.findall(r"\b(?:19|20)\d{2}\b", text))


# Checks for common placeholder patterns in the text, which may indicate fabrication or incomplete content.
def contains_placeholder(text: str):
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True, pattern
    return False, ""


# Computes a simple keyword overlap score between the JD text and the final tailored resume text, ignoring common stopwords.
def keyword_overlap_score(jd_text: str, final_text: str) -> tuple[int, list[str]]:
    jd_tokens = set(
        w.lower()
        for w in re.findall(r"[A-Za-z][A-Za-z\-/+]{2,}", jd_text)
        if w.lower() not in STOPWORDS
    )

    final_norm = normalize_text(final_text)
    matched = []

    for token in sorted(jd_tokens):
        token_norm = normalize_text(token)
        if not token_norm:
            continue

        pattern = r"\b" + re.escape(token_norm).replace(r"\ ", r"\s+") + r"\b"
        if re.search(pattern, final_norm):
            matched.append(token)

    return len(matched), matched


# Functional test: verifies the /health endpoint is responsive and returns status 200.
def run_health_check():
    name = "Functional testing - /health endpoint"
    try:
        response = requests.get(f"{API_URL}/health", timeout=20)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print_result(name, True)
    except Exception as e:
        print_result(name, False, str(e))


# Functional test: verifies that the /analyze endpoint returns an error when the PDF file is missing.
def run_missing_pdf_test():
    name = "Functional testing - missing PDF request"
    try:
        response = requests.post(
            f"{API_URL}/analyze",
            data={"jd_text": SAMPLE_JD},
            timeout=60,
        )
        assert response.status_code in {400, 415, 422}, f"Expected 400/415/422, got {response.status_code}"
        print_result(name, True, f"Returned {response.status_code} as expected")
    except Exception as e:
        print_result(name, False, str(e))

# End-to-end test: verifies the full workflow from PDF input to structured JSON output, and checks basic content sanity.
def run_end_to_end_test():
    name = "End-to-end testing - FastAPI API contract"
    try:
        result = analyze_resume(SAMPLE_JD, SAMPLE_PDF_PATH)
        response = result["response"]

        assert result["status_code"] == 200, f"Expected 200, got {result['status_code']}"

        payload = response.json()
        assert "alignment" in payload, "Missing top-level field: alignment"
        assert "tailored_resume" in payload, "Missing top-level field: tailored_resume"

        alignment = safe_json_load(payload["alignment"], "alignment")
        tailored = safe_json_load(payload["tailored_resume"], "tailored_resume")

        assert isinstance(alignment.get("matched", []), list), "alignment.matched must be a list"
        assert isinstance(alignment.get("missing", []), list), "alignment.missing must be a list"
        assert isinstance(alignment.get("weak_matches", []), list), "alignment.weak_matches must be a list"

        final_text = get_final_resume_text(tailored)
        assert final_text.strip(), "Final tailored resume text is empty"

        details = (
            f"matched={len(alignment.get('matched', []))}, "
            f"missing={len(alignment.get('missing', []))}, "
            f"weak_matches={len(alignment.get('weak_matches', []))}"
        )
        print_result(name, True, details)

        return payload, alignment, tailored, final_text

    except Exception as e:
        print_result(name, False, str(e))
        return None, None, None, None


# Factual consistency test: checks for empty output, placeholder content, unsupported year fabrication, and presence of rewritten bullet metadata.
def run_factual_consistency_test(pdf_text: str, tailored: dict, final_text: str):
    name = "Factual consistency - no obvious fabrication / placeholders"
    try:
        assert final_text.strip(), "Final text is empty"

        found_placeholder, pattern = contains_placeholder(final_text)
        assert not found_placeholder, f"Found placeholder-like content matching: {pattern}"

        source_years = extract_years(pdf_text)
        final_years = extract_years(final_text)
        new_years = final_years - source_years

        assert not new_years, f"Potential unsupported year(s) introduced: {sorted(new_years)}"

        rewritten_bullets = tailored.get("rewritten_bullets", [])
        for i, item in enumerate(rewritten_bullets, start=1):
            original = item.get("original", "").strip()
            revised = item.get("revised", "").strip()
            assert original, f"rewritten_bullets[{i}] missing original"
            assert revised, f"rewritten_bullets[{i}] missing revised"

        print_result(name, True)
    except Exception as e:
        print_result(name, False, str(e))


# Alignment quality test: checks that the alignment report contains expected fields, that the final text reflects JD relevance, and that required skills are present.
def run_alignment_quality_test(alignment: dict, tailored: dict, final_text: str):
    name = "Alignment quality - JD relevance appears in output"
    try:
        matched = alignment.get("matched", [])
        missing = alignment.get("missing", [])
        weak_matches = alignment.get("weak_matches", [])

        total_alignment_items = len(matched) + len(missing) + len(weak_matches)
        assert total_alignment_items > 0, "Alignment report is empty"
        assert len(matched) > 0 or len(weak_matches) > 0, "No matched or weak matches found"

        overlap_count, overlap_terms = keyword_overlap_score(SAMPLE_JD, final_text)
        assert overlap_count >= 5, (
            f"Too few JD-related terms found in final output: {overlap_count} "
            f"(terms: {overlap_terms[:10]})"
        )

        skills = tailored.get("reordered_skills", []) or tailored.get("skills", [])
        skills_lower = " | ".join(skills).lower() if isinstance(skills, list) else str(skills).lower()
        skill_hits = [skill for skill in REQUIRED_SKILLS if skill in skills_lower or skill in final_text.lower()]

        assert len(skill_hits) >= 2, f"Too few required skills reflected in output: {skill_hits}"

        # Check whether JD-related skills are placed near the top of reordered skills.
        if isinstance(skills, list) and skills:
            top_skills = [s.lower() for s in skills[:5]]
            top_hits = [skill for skill in REQUIRED_SKILLS if skill in " | ".join(top_skills)]
            assert top_hits, f"No required skills appear in the top reordered skills: {skills[:5]}"

        print_result(
            name,
            True,
            f"keyword_overlap={overlap_count}, required_skill_hits={skill_hits}"
        )
    except Exception as e:
        print_result(name, False, str(e))


# JSON structure test: verifies that the alignment and tailored_resume fields have the expected structure and required subfields.
def run_json_structure_test(payload: dict):
    name = "Functional testing - JSON structure validation"
    try:
        alignment = safe_json_load(payload["alignment"], "alignment")
        tailored = safe_json_load(payload["tailored_resume"], "tailored_resume")

        # alignment structure
        assert "matched" in alignment, "alignment missing key: matched"
        assert "missing" in alignment, "alignment missing key: missing"
        assert "weak_matches" in alignment, "alignment missing key: weak_matches"

        # tailored structure: accept either full text or preview mode
        has_full_text = bool(tailored.get("full_resume_text", "").strip())
        has_preview_mode = all(
            key in tailored for key in ["professional_summary", "reordered_skills", "rewritten_bullets"]
        )

        assert has_full_text or has_preview_mode, (
            "tailored_resume must contain either full_resume_text "
            "or preview fields (professional_summary, reordered_skills, rewritten_bullets)"
        )

        # Ensure preview mode contains expected bullet metadata if present
        if not has_full_text and has_preview_mode:
            assert isinstance(tailored.get("rewritten_bullets"), list), "rewritten_bullets must be a list"

        print_result(name, True)
    except Exception as e:
        print_result(name, False, str(e))


# Export content test: verifies that the PDF, text, and JSON exports can be generated without error, and that they contain expected content patterns.
def run_export_format_test(payload: dict):
    name = "Functional testing - PDF, text, and JSON export generation"
    try:
        tailored = safe_json_load(payload["tailored_resume"], "tailored_resume")
        pdf_bytes, plain_text, json_text = build_export_outputs(tailored)

        # PDF export checks
        assert isinstance(pdf_bytes, (bytes, bytearray)), "PDF export is not bytes"
        assert len(pdf_bytes) > 100, f"PDF export looks too small: {len(pdf_bytes)} bytes"
        assert pdf_bytes[:4] == b"%PDF", "PDF export does not start with a valid PDF header"

        # Text export checks
        assert isinstance(plain_text, str), "Text export is not a string"
        assert plain_text.strip(), "Text export is empty"
        assert "TAILORED RESUME" in plain_text or len(plain_text) > 50, "Text export content looks incomplete"

        # JSON export checks
        assert isinstance(json_text, str), "JSON export is not a string"
        assert json_text.strip(), "JSON export is empty"
        assert json.loads(json_text) == tailored, "JSON export cannot be parsed back correctly"

        print_result(
            name,
            True,
            f"pdf_bytes={len(pdf_bytes)}, text_chars={len(plain_text)}, json_chars={len(json_text)}"
        )
    except Exception as e:
        print_result(name, False, str(e))


# Source overlap test: applies a normalized-text heuristic to check whether
# rewritten bullets can be traced back to the source PDF text.
def run_source_overlap_test(pdf_text: str, tailored: dict, final_text: str, _alignment: dict):
    name = "Factual consistency - source overlap heuristic"
    try:
        pdf_norm = normalize_text(pdf_text)
        final_norm = normalize_text(final_text)

        rewritten_bullets = tailored.get("rewritten_bullets", [])
        for i, item in enumerate(rewritten_bullets, start=1):
            original = item.get("original", "").strip()
            if original:
                snippet_norm = normalize_text(original[:50])
                assert snippet_norm in pdf_norm, (
                    f"rewritten_bullets[{i}].original not found in normalized source PDF text: {original[:50]}"
                )

        overlap_count, _ = keyword_overlap_score(pdf_text, final_text)
        assert overlap_count >= 3, (
            f"Final resume text has too little lexical overlap with source resume: {overlap_count}"
        )

        assert final_norm, "Normalized final text is empty"

        print_result(name, True)
    except Exception as e:
        print_result(name, False, str(e))

def main():
    print("=" * 72)
    print("Resume Tailoring Assistant - Prototype Testing")
    print(f"API_URL         : {API_URL}")
    print(f"SAMPLE_PDF_PATH : {SAMPLE_PDF_PATH}")
    print("=" * 72)

    try:
        pdf_text = extract_pdf_text(SAMPLE_PDF_PATH)
    except Exception as e:
        print_result("Setup - sample resume PDF loading", False, str(e))
        return

    print_result("Setup - sample resume PDF loading", True)

    # 1) Functional testing
    run_health_check()
    run_missing_pdf_test()

    # 2) End-to-end testing
    payload, alignment, tailored, final_text = run_end_to_end_test()

    if payload is None:
        print("\nStopped because end-to-end test failed.")
        return

    # 3) Functional testing - structure
    run_json_structure_test(payload)
    run_export_format_test(payload)

    # 4) Factual consistency
    run_factual_consistency_test(pdf_text, tailored, final_text)
    run_source_overlap_test(pdf_text, tailored, final_text, alignment)

    # 5) Alignment quality
    run_alignment_quality_test(alignment, tailored, final_text)

    print("\nDone.")


if __name__ == "__main__":
    main()