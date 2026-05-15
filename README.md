# AI Resume Tailoring Assistant

An AI-powered web tool that helps job seekers tailor an existing resume to a specific job description. It performs **structured gap analysis** between a target job posting and a candidate's resume, then produces a **rewritten resume** that emphasises the requirements the candidate already meets — without inventing experience.

The system combines **semantic embeddings** (`all-MiniLM-L6-v2`) for grounded similarity scoring with **Google Gemini** for parsing, reasoning, and controlled rewriting, in a transparent five-stage pipeline.

---

## Features

- **Single-input UX** — paste a job description, upload a PDF resume, click *Tailor My Resume*.
- **Structured gap analysis** — every JD requirement is classified as *matched*, *weak*, or *missing*, with evidence from the resume.
- **Faithful rewriting** — the generator preserves original facts and bullet structure while emphasising covered requirements.
- **Multiple export formats** — PDF, plain text, and JSON (for ATS submission or downstream tooling).
- **Auditable intermediate outputs** — each stage's JSON is returned to the frontend, so users see *why* the system reached its verdict.

---

## Architecture

```
   ┌────────────┐   ┌────────────────┐
   │  Stage 1   │   │    Stage 2     │   (parallel,
   │ JD parser  │   │ Resume parser  │    ThreadPoolExecutor)
   │   (LLM)    │   │     (LLM)      │
   └─────┬──────┘   └────────┬───────┘
         └────────┬──────────┘
                  ▼
         ┌─────────────────┐
         │   Stage 2.5     │
         │ Embedding scorer│   ← SentenceTransformer (no LLM call)
         │ (MiniLM-L6-v2)  │
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │     Stage 3     │
         │ Alignment       │   ← LLM grounded by embedding scores
         │  analyser       │
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │     Stage 4     │
         │ Tailored-bullet │   ← LLM rewrite
         │   generator     │
         └────────┬────────┘
                  ▼
              Frontend
```

| Layer | Tech | Entry point |
|---|---|---|
| Frontend | Streamlit | [`frontend/app.py`](frontend/app.py) |
| Backend  | FastAPI   | [`backend/main.py`](backend/main.py) |
| LLM      | Google Gemini (`google-genai`) | [`backend/llm_client.py`](backend/llm_client.py) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | [`backend/modules/embedding_matcher.py`](backend/modules/embedding_matcher.py) |
| PDF I/O  | `pdfplumber` (read), `reportlab` (write) | [`backend/utils.py`](backend/utils.py), [`frontend/pdf_export.py`](frontend/pdf_export.py) |

---

## Setup

```bash
# 1. Create and activate a virtual environment (Python 3.11 recommended)
python3.11 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API key
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your-key-from-https://aistudio.google.com/apikey
```

## Run

Open two terminals:

```bash
# Terminal 1 — backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
streamlit run frontend/app.py
```

Then open <http://localhost:8501> in your browser.

---

## Repository layout

```
backend/
  main.py                  FastAPI app, /analyze endpoint, pipeline orchestration
  llm_client.py            Shared Gemini client
  utils.py                 PDF text extraction (pdfplumber)
  modules/
    jd_parser.py           Stage 1 — JD → structured JSON
    resume_parser.py       Stage 2 — Resume → structured JSON
    embedding_matcher.py   Stage 2.5 — semantic similarity scoring
    alignment.py           Stage 3 — LLM gap analysis (embedding-grounded)
    generator.py           Stage 4 — tailored resume rewrite
frontend/
  app.py                   Streamlit input page
  pages/1_Results.py       Results, matching, and export page
  pdf_export.py            PDF generation (reportlab)
tests/
  run_jd_parser.py         Manual parser smoke test
  run_resume_parser.py     Manual parser smoke test
  run_evaluation.py        Semantic-embedding evaluation vs Kaggle ground truth
```

---

## Evaluation

A reproducible evaluation of the embedding scorer against the Kaggle [*Resume Dataset*](https://www.kaggle.com/datasets/saugataroyarghya/resume-dataset) (9,544 resume–job pairs) is provided in [`tests/run_evaluation.py`](tests/run_evaluation.py). It reports Pearson *r* and Spearman ρ between the system's `overall_match_score` and the dataset's ground-truth `matched_score`.

```bash
.venv/bin/python tests/run_evaluation.py /path/to/resume_data.csv
```

---

## Team

| Module | Owner |
|---|---|
| Architecture, orchestration, integration | Yufan Gong |
| Stage 1 — JD parser | Nguyen Thao Nhi Truong |
| Stage 2 — Resume parser | Lin Li |
| Stage 2.5 / 3 — Embedding & alignment | Jinyu Yan |
| Stage 4 — Generator | Myeongjin Han |
| Frontend & export | Lujia Ouyang |
