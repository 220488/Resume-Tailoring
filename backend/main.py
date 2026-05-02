from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import tempfile
import os
import json

from backend.file_extractors import extract_resume_text
from backend.modules.resume_parser import parse_resume
from backend.modules.tailored_resume_generator import generate_tailored_resume_json

app = FastAPI()


@app.post("/analyze")
async def analyze(
    jd_text: str = Form(...),
    resume_pdf: UploadFile = File(...)
):
    suffix = os.path.splitext(resume_pdf.filename)[1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await resume_pdf.read())
        temp_path = tmp.name

    try:
        # 1. PDF -> text
        resume_text = extract_resume_text(temp_path)

        # 2. Resume parsing
        resume_parsed_str = parse_resume(resume_text)

        # 3. Placeholder JD parsing result for now
        jd_parsed_str = json.dumps({
            "job_title": None,
            "required_skills": [],
            "preferred_skills": [],
            "role_keywords": [],
            "responsibilities": [],
            "experience": {}
        })

        # 4. Placeholder alignment result for now
        alignment_str = json.dumps({
            "matched": [],
            "missing": [],
            "weak_matches": []
        })

        # 5. Tailored resume generation
        tailored_resume_str = generate_tailored_resume_json(
            jd_json=jd_parsed_str,
            resume_json=resume_parsed_str,
            alignment_json=alignment_str,
            use_api=False
        )

        return {
            "jd_parsed": jd_parsed_str,
            "resume_parsed": resume_parsed_str,
            "alignment": alignment_str,
            "tailored_resume": tailored_resume_str
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.get("/health")
def health():
    return {"status": "ok"}